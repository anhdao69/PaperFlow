import SwiftData
import XCTest
@testable import PaperFlow

@MainActor
final class PersonalStateMachineTests: XCTestCase {
    func testInitialSaveAndSkipFollowCanonicalStateTable() throws {
        let (store, service) = try makeService(times: [date(1), date(2)])

        let saved = try service.save(paper("2608.10001v1"))
        XCTAssertEqual(saved.canonicalArxivID, "2608.10001")
        XCTAssertTrue(saved.seen)
        XCTAssertTrue(saved.saved)
        XCTAssertEqual(saved.savedAt, date(1))
        XCTAssertEqual(saved.lastSavedAt, date(1))
        XCTAssertEqual(saved.lastSeenAt, date(1))
        XCTAssertEqual(saved.readingStatus, .queue)
        XCTAssertNotNil(saved.snapshot)

        let skipped = try service.skip(arxivID: "2608.10002v2")
        XCTAssertTrue(skipped.seen)
        XCTAssertFalse(skipped.saved)
        XCTAssertEqual(skipped.lastSeenAt, date(2))
        XCTAssertNil(skipped.readingStatus)
        XCTAssertEqual(try store.allStates().count, 2)
    }

    func testRepeatedSaveIsIdempotentAndPreservesReadingAndDone() throws {
        let (_, service) = try makeService(
            times: [date(1), date(2), date(3), date(4), date(5)]
        )
        let item = paper("2608.10003")
        let state = try service.save(item)
        try service.transition(arxivID: item.arxivId, to: .reading)
        let firstSave = state.savedAt
        let lastSave = state.lastSavedAt
        let statusAt = state.statusChangedAt

        try service.save(item)
        XCTAssertEqual(state.readingStatus, .reading)
        XCTAssertEqual(state.savedAt, firstSave)
        XCTAssertEqual(state.lastSavedAt, lastSave)
        XCTAssertEqual(state.statusChangedAt, statusAt)
        XCTAssertEqual(state.lastSeenAt, date(3))

        try service.transition(arxivID: item.arxivId, to: .done)
        let completedAt = state.completedAt
        try service.save(item)
        XCTAssertEqual(state.readingStatus, .done)
        XCTAssertEqual(state.completedAt, completedAt)
        XCTAssertEqual(state.lastSavedAt, lastSave)
    }

    func testSkipSavedPaperNeverUnsavesOrResetsStatus() throws {
        let (_, service) = try makeService(times: [date(1), date(2), date(3)])
        let item = paper("2608.10004")
        let state = try service.save(item)
        try service.transition(arxivID: item.arxivId, to: .reading)
        let statusAt = state.statusChangedAt

        try service.skip(arxivID: item.arxivId)

        XCTAssertTrue(state.saved)
        XCTAssertEqual(state.readingStatus, .reading)
        XCTAssertEqual(state.statusChangedAt, statusAt)
        XCTAssertEqual(state.lastSeenAt, date(3))
    }

    func testUnsaveAndResaveRetainHistoryAndSnapshot() throws {
        let (_, service) = try makeService(
            times: [date(1), date(2), date(3), date(4), date(5), date(6), date(7)]
        )
        let item = paper("2608.10005")
        let state = try service.save(item)
        try service.transition(arxivID: item.arxivId, to: .reading)
        try service.markOpened(arxivID: item.arxivId)
        try service.updateNote(arxivID: item.arxivId, note: "Remember this")
        try service.updateRating(arxivID: item.arxivId, rating: 5)
        let retained = PersonalPaperStateValue(state)

        try service.unsave(arxivID: item.arxivId)
        XCTAssertFalse(state.saved)
        XCTAssertEqual(state.unsavedAt, date(4))
        XCTAssertEqual(state.note, retained.note)
        XCTAssertEqual(state.rating, retained.rating)
        XCTAssertEqual(state.snapshot?.title, retained.snapshot?.title)

        try service.save(item)
        XCTAssertTrue(state.saved)
        XCTAssertNil(state.unsavedAt)
        XCTAssertEqual(state.savedAt, retained.savedAt)
        XCTAssertEqual(state.lastSavedAt, date(5))
        XCTAssertEqual(state.readingStatus, retained.readingStatus)
        XCTAssertEqual(state.startedReadingAt, retained.startedReadingAt)
        XCTAssertEqual(state.lastOpenedAt, retained.lastOpenedAt)
        XCTAssertEqual(state.note, retained.note)
        XCTAssertEqual(state.rating, retained.rating)
    }

    func testReadingTransitionsAndTimestamps() throws {
        let (_, service) = try makeService(
            times: [date(1), date(2), date(3), date(4), date(5)]
        )
        let item = paper("2608.10006")
        let state = try service.save(item)

        try service.transition(arxivID: item.arxivId, to: .reading)
        XCTAssertEqual(state.startedReadingAt, date(2))
        XCTAssertNil(state.completedAt)

        try service.transition(arxivID: item.arxivId, to: .done)
        XCTAssertEqual(state.completedAt, date(3))

        try service.transition(arxivID: item.arxivId, to: .queue)
        XCTAssertNil(state.completedAt)

        try service.transition(arxivID: item.arxivId, to: .reading)
        XCTAssertEqual(state.startedReadingAt, date(5))
        XCTAssertNil(state.completedAt)
    }

    func testUnsavedStateRejectsSavedOnlyMutationsAndInvalidRating() throws {
        let (_, service) = try makeService(times: [])
        XCTAssertThrowsError(
            try service.transition(arxivID: "2608.10007", to: .reading)
        )
        XCTAssertThrowsError(
            try service.updateNote(arxivID: "2608.10007", note: "No")
        )
        XCTAssertThrowsError(
            try service.updateRating(arxivID: "2608.10007", rating: 6)
        )
    }

    func testLastOpenedOnlyChangesForSavedPaper() throws {
        let (_, service) = try makeService(times: [date(1), date(2), date(3)])
        XCTAssertNil(try service.markOpened(arxivID: "2608.10008"))
        let state = try service.save(paper("2608.10008"))
        try service.markOpened(arxivID: state.canonicalArxivID)
        XCTAssertEqual(state.lastOpenedAt, date(2))
        try service.unsave(arxivID: state.canonicalArxivID)
        XCTAssertNil(try service.markOpened(arxivID: state.canonicalArxivID))
        XCTAssertEqual(state.lastOpenedAt, date(2))
    }

    func testUndoRestoresExactPriorStateAndRemovesNewRecord() throws {
        let (store, service) = try makeService(
            times: [date(1), date(2), date(3), date(4), date(5)]
        )
        let existing = paper("2608.10009")
        let state = try service.save(existing)
        try service.transition(arxivID: existing.arxivId, to: .reading)
        let prior = PersonalPaperStateValue(state)

        try service.save(existing, registersUndo: true)
        let restored = try XCTUnwrap(try service.undoLastAction())
        XCTAssertEqual(PersonalPaperStateValue(restored), prior)
        XCTAssertNil(service.undoSnapshot)

        let newID = "2608.10010"
        try service.skip(arxivID: newID, registersUndo: true)
        XCTAssertNotNil(try store.state(for: newID))
        XCTAssertNil(try service.undoLastAction())
        XCTAssertNil(try store.state(for: newID))
        XCTAssertThrowsError(try service.undoLastAction())
    }

    func testVersionedIDsConvergeToOneRecord() throws {
        let (store, service) = try makeService(times: [date(1), date(2)])
        try service.skip(arxivID: "2608.10011v1")
        try service.save(paper("2608.10011v2"))

        XCTAssertEqual(try store.allStates().count, 1)
        XCTAssertTrue(try XCTUnwrap(store.state(for: "2608.10011")).saved)
    }

    func testFailedCommitRollsBackNewRecord() throws {
        let store = FailingPersonalPaperStore()
        let service = PersonalActionService(store: store, clock: { self.date(1) })

        XCTAssertThrowsError(try service.save(paper("2608.10012")))
        XCTAssertNil(try store.state(for: "2608.10012"))
    }

    func testFailedTransactionLeavesPersistedPriorRecordIntact() throws {
        let (store, service) = try makeService(times: [date(1)])
        let item = paper("2608.10013")
        let state = try service.save(item)
        let prior = PersonalPaperStateValue(state)
        let failingService = PersonalActionService(
            store: FailingCommitStore(base: store),
            clock: { self.date(2) }
        )

        XCTAssertThrowsError(try failingService.skip(arxivID: item.arxivId))

        let restored = try XCTUnwrap(store.state(for: item.arxivId))
        XCTAssertEqual(PersonalPaperStateValue(restored), prior)
    }

    private func makeService(
        times: [Date]
    ) throws -> (SwiftDataPersonalPaperStore, PersonalActionService) {
        let schema = Schema([PersonalPaperState.self, SavedPaperSnapshot.self])
        let configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
        let container = try ModelContainer(for: schema, configurations: [configuration])
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        var iterator = times.makeIterator()
        let service = PersonalActionService(store: store) {
            iterator.next() ?? self.date(99)
        }
        return (store, service)
    }

    private func date(_ hour: Int) -> Date {
        Date(timeIntervalSince1970: TimeInterval(hour * 3_600))
    }

    private func paper(_ id: String) -> PublicPaper {
        PublicPaper(
            arxivId: id,
            title: "Paper \(id)",
            authors: ["Ada Researcher"],
            abstract: "A deterministic fixture abstract.",
            arxivUrl: URL(string: "https://arxiv.org/abs/2608.10000")!,
            pdfUrl: URL(string: "https://arxiv.org/pdf/2608.10000")!,
            firstSeenAt: date(0),
            categories: ["cs.AI"],
            relevance: 9,
            novelty: 8,
            topicAssignments: [
                TopicAssignment(topicId: "world-models", subtopicIds: ["video-world-models"])
            ],
            selectionReason: "Fixture",
            tldr: "Fixture summary",
            bullets: ["One", "Two", "Three"],
            summaryStatus: .generated,
            heroFigure: nil,
            figureStatus: .notImplemented
        )
    }
}

@MainActor
private final class FailingPersonalPaperStore: PersonalPaperStore {
    private enum Failure: Error { case forced }
    private var states: [String: PersonalPaperState] = [:]
    private var insertedSnapshots: [SavedPaperSnapshot] = []

    func state(for canonicalArxivID: String) throws -> PersonalPaperState? {
        states[PublicPaper.normalizeArxivID(canonicalArxivID)]
    }

    func allStates() throws -> [PersonalPaperState] { Array(states.values) }

    func insert(_ state: PersonalPaperState) { states[state.canonicalArxivID] = state }
    func insert(_ snapshot: SavedPaperSnapshot) { insertedSnapshots.append(snapshot) }
    func delete(_ state: PersonalPaperState) { states[state.canonicalArxivID] = nil }
    func delete(_ snapshot: SavedPaperSnapshot) {
        insertedSnapshots.removeAll { $0 === snapshot }
    }
    func commit() throws { throw Failure.forced }
    func rollback() {
        states.removeAll()
        insertedSnapshots.removeAll()
    }
}

@MainActor
private final class FailingCommitStore: PersonalPaperStore {
    private enum Failure: Error { case forced }
    private let base: SwiftDataPersonalPaperStore

    init(base: SwiftDataPersonalPaperStore) {
        self.base = base
    }

    func state(for canonicalArxivID: String) throws -> PersonalPaperState? {
        try base.state(for: canonicalArxivID)
    }

    func allStates() throws -> [PersonalPaperState] { try base.allStates() }
    func insert(_ state: PersonalPaperState) { base.insert(state) }
    func insert(_ snapshot: SavedPaperSnapshot) { base.insert(snapshot) }
    func delete(_ state: PersonalPaperState) { base.delete(state) }
    func delete(_ snapshot: SavedPaperSnapshot) { base.delete(snapshot) }
    func commit() throws { throw Failure.forced }
    func rollback() { base.rollback() }
}
