import SwiftData
import XCTest
@testable import PaperFlow

@MainActor
final class SwipeSessionTests: XCTestCase {
    func testDefaultEligibilityUsesGlobalSeenStateAndProgressDenominator() throws {
        let (store, service) = try makeStore(times: [date(1)])
        let first = swipePaper("2608.20001", topic: "a")
        let second = swipePaper("2608.20002", topic: "a")
        try service.skip(arxivID: first.arxivId)
        let session = SwipeSessionViewModel(
            collection: collection([first, second]),
            store: store,
            actions: service
        )

        XCTAssertEqual(session.currentPaper?.arxivId, second.arxivId)
        XCTAssertEqual(session.progress, CollectionProgress(reviewed: 1, total: 2))
        XCTAssertEqual(session.remainingSessionCount, 1)
    }

    func testTopicFilterChangesActiveDenominatorBeforeReviewMode() throws {
        let (store, service) = try makeStore(times: [date(1)])
        let first = swipePaper("2608.20003", topic: "a")
        let second = swipePaper("2608.20004", topic: "b")
        try service.skip(arxivID: second.arxivId)
        let session = SwipeSessionViewModel(
            collection: collection([first, second]),
            store: store,
            actions: service
        )

        session.selectedTopicIDs = ["b"]

        XCTAssertEqual(session.progress, CollectionProgress(reviewed: 1, total: 1))
        XCTAssertNil(session.currentPaper)
    }

    func testSaveAndSkipCommandsFollowCanonicalSemantics() throws {
        let (store, service) = try makeStore(times: [date(1), date(2), date(3), date(4)])
        let saved = swipePaper("2608.20005", topic: "a")
        let skipped = swipePaper("2608.20006", topic: "a")
        let session = SwipeSessionViewModel(
            collection: collection([saved, skipped]),
            store: store,
            actions: service
        )

        try session.perform(.save)
        let savedState = try XCTUnwrap(store.state(for: saved.arxivId))
        XCTAssertTrue(savedState.saved)
        XCTAssertTrue(savedState.seen)
        XCTAssertEqual(savedState.readingStatus, .queue)

        try session.perform(.skip)
        let skippedState = try XCTUnwrap(store.state(for: skipped.arxivId))
        XCTAssertTrue(skippedState.seen)
        XCTAssertFalse(skippedState.saved)
        XCTAssertTrue(session.isComplete)
    }

    func testSkipAlreadySavedAndSaveReadingPaperPreserveMembershipAndStatus() throws {
        let (store, service) = try makeStore(
            times: [date(1), date(2), date(3), date(4), date(5)]
        )
        let first = swipePaper("2608.20007", topic: "a")
        let second = swipePaper("2608.20008", topic: "a")
        try service.save(first)
        try service.transition(arxivID: first.arxivId, to: .done)
        try service.save(second)
        try service.transition(arxivID: second.arxivId, to: .reading)
        let session = SwipeSessionViewModel(
            collection: collection([first, second]),
            store: store,
            actions: service
        )
        session.reviewMode = .all

        try session.perform(.skip)
        XCTAssertTrue(try XCTUnwrap(store.state(for: first.arxivId)).saved)
        XCTAssertEqual(try store.state(for: first.arxivId)?.readingStatus, .done)
        try session.perform(.save)
        XCTAssertEqual(try store.state(for: second.arxivId)?.readingStatus, .reading)
    }

    func testUndoRestoresExactPriorStateAndCardPosition() throws {
        let (store, service) = try makeStore(times: [date(1), date(2), date(3)])
        let first = swipePaper("2608.20009", topic: "a")
        let second = swipePaper("2608.20010", topic: "a")
        let session = SwipeSessionViewModel(
            collection: collection([first, second]),
            store: store,
            actions: service
        )

        try session.perform(.save)
        XCTAssertEqual(session.currentPaper?.arxivId, second.arxivId)
        XCTAssertTrue(session.canUndo)
        try session.undo()

        XCTAssertEqual(session.currentPaper?.arxivId, first.arxivId)
        XCTAssertNil(try store.state(for: first.arxivId))
        XCTAssertFalse(session.canUndo)
        XCTAssertThrowsError(try session.undo())
    }

    func testUndoExistingSavedSkipRestoresAllPersonalFields() throws {
        let (store, service) = try makeStore(
            times: [date(1), date(2), date(3), date(4), date(5)]
        )
        let item = swipePaper("2608.20011", topic: "a")
        let state = try service.save(item)
        try service.transition(arxivID: item.arxivId, to: .reading)
        try service.updateNote(arxivID: item.arxivId, note: "Keep")
        let prior = PersonalPaperStateValue(state)
        let session = SwipeSessionViewModel(
            collection: collection([item]),
            store: store,
            actions: service
        )
        session.reviewMode = .all

        try session.perform(.skip)
        try session.undo()

        XCTAssertEqual(PersonalPaperStateValue(try XCTUnwrap(store.state(for: item.arxivId))), prior)
    }

    func testRestartResumesAtFirstGloballyUnreviewedPaper() throws {
        let (store, firstService) = try makeStore(times: [date(1)])
        let papers = [
            swipePaper("2608.20012", topic: "a"),
            swipePaper("2608.20013", topic: "a")
        ]
        let firstSession = SwipeSessionViewModel(
            collection: collection(papers),
            store: store,
            actions: firstService
        )
        try firstSession.perform(.skip)

        let recreated = SwipeSessionViewModel(
            collection: collection(papers),
            store: store,
            actions: PersonalActionService(store: store, clock: { self.date(2) })
        )

        XCTAssertEqual(recreated.currentPaper?.arxivId, papers[1].arxivId)
        XCTAssertEqual(recreated.remainingSessionCount, 1)
    }

    func testOpeningDetailWithoutDecisionLeavesSessionUnchanged() throws {
        let (store, service) = try makeStore(times: [])
        let item = swipePaper("2608.20014", topic: "a")
        let session = SwipeSessionViewModel(
            collection: collection([item]),
            store: store,
            actions: service
        )
        let before = session.currentPaper

        session.synchronizePersonalState()

        XCTAssertEqual(session.currentPaper, before)
        XCTAssertNil(try store.state(for: item.arxivId))
        XCTAssertFalse(session.canUndo)
    }

    private func makeStore(
        times: [Date]
    ) throws -> (SwiftDataPersonalPaperStore, PersonalActionService) {
        let container = try ModelContainer(
            for: PersonalPaperState.self,
            SavedPaperSnapshot.self,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        var values = times
        let service = PersonalActionService(store: store) {
            values.isEmpty ? self.date(99) : values.removeFirst()
        }
        return (store, service)
    }

    private func collection(_ papers: [PublicPaper]) -> SwipeCollection {
        SwipeCollection(id: "test", title: "Test", papers: papers)
    }

    private func date(_ value: Int) -> Date {
        Date(timeIntervalSince1970: TimeInterval(value * 60))
    }
}

private func swipePaper(_ id: String, topic: String) -> PublicPaper {
    PublicPaper(
        arxivId: id,
        title: "Paper \(id)",
        authors: ["Test Author"],
        abstract: "A complete abstract.",
        arxivUrl: URL(string: "https://arxiv.org/abs/\(id)")!,
        pdfUrl: URL(string: "https://arxiv.org/pdf/\(id)")!,
        firstSeenAt: Date(timeIntervalSince1970: 100),
        categories: ["cs.AI"],
        relevance: 9,
        novelty: 8,
        topicAssignments: [TopicAssignment(topicId: topic, subtopicIds: [])],
        selectionReason: "Relevant",
        tldr: nil,
        bullets: [],
        summaryStatus: .failed,
        heroFigure: nil,
        figureStatus: .notImplemented
    )
}
