import SwiftData
import XCTest
@testable import PaperFlow

@MainActor
final class TopicsViewModelTests: XCTestCase {
    func testHierarchyAndUniqueTotalAreEntirelyPublishedDataDriven() {
        let index = TopicsIndex(
            schemaVersion: 1,
            taxonomyVersion: 42,
            totalPaperCount: 7,
            topics: [
                PublicTopic(
                    id: "renamed-at-runtime",
                    name: "A Runtime Taxonomy Name",
                    paperCount: 6,
                    feedUrl: "published/runtime/all.json",
                    subtopics: [
                        PublicSubtopic(
                            id: "runtime-child",
                            name: "Runtime Child",
                            paperCount: 4,
                            feedUrl: "published/runtime/child.json"
                        )
                    ]
                ),
                PublicTopic(
                    id: "overlap",
                    name: "Overlapping Topic",
                    paperCount: 5,
                    feedUrl: "published/overlap/all.json",
                    subtopics: []
                )
            ]
        )

        XCTAssertEqual(TopicsViewModel.uniqueTotal(index), 7)
        XCTAssertNotEqual(TopicsViewModel.uniqueTotal(index), 11)
        XCTAssertEqual(
            TopicsViewModel.topic(for: "renamed-at-runtime", in: index)?.name,
            "A Runtime Taxonomy Name"
        )
        XCTAssertEqual(index.topics[0].subtopics[0].feedUrl, "published/runtime/child.json")
    }

    func testAppModelConsumesExplicitTopicURLWithoutDerivingFromID() async {
        let client = RecordingTopicClient()
        let model = AppModel(client: client)
        let explicit = "published/non-derived/location.json"

        await model.loadTopicFeed(relativePath: explicit)

        let requestedPath = await client.requestedPath()
        XCTAssertEqual(requestedPath, explicit)
        XCTAssertNotNil(model.topicFeeds[explicit])
    }

    func testHistoryUsesExactFeedMembershipDayCountsAndFilters() {
        let first = topicPaper("2608.30001", topics: [("a", ["a1"]), ("b", ["b1"])])
        let second = topicPaper("2608.30002", topics: [("a", ["a2"])])
        let feed = TopicFeed(
            schemaVersion: 1,
            topicId: "a",
            subtopicId: nil,
            totalPaperCount: 2,
            days: [
                TopicFeedDay(date: Date(timeIntervalSince1970: 200), paperCount: 1, papers: [first]),
                TopicFeedDay(date: Date(timeIntervalSince1970: 100), paperCount: 1, papers: [second])
            ]
        )
        let topic = PublicTopic(
            id: "a",
            name: "A",
            paperCount: 2,
            feedUrl: "data/a.json",
            subtopics: [
                PublicSubtopic(id: "a1", name: "A1", paperCount: 1, feedUrl: "data/a1.json"),
                PublicSubtopic(id: "a2", name: "A2", paperCount: 1, feedUrl: "data/a2.json")
            ]
        )
        let state = PersonalPaperState(canonicalArxivID: first.arxivId)
        state.seen = true
        state.saved = true
        let model = TopicHistoryViewModel(feed: feed, topic: topic)

        XCTAssertEqual(model.dayCounts.map(\.count), [1, 1])
        XCTAssertEqual(model.papers.map(\.arxivId), [first.arxivId, second.arxivId])
        model.status = .unread
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.arxivId), [second.arxivId])
        model.status = .saved
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.arxivId), [first.arxivId])
        model.status = .all
        model.selectedSubtopicIDs = ["a2"]
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.arxivId), [second.arxivId])
    }

    func testMultiTopicPaperSharesOneGlobalStateAndDefaultTopicDeckExcludesReviewed() throws {
        let container = try ModelContainer(
            for: PersonalPaperState.self,
            SavedPaperSnapshot.self,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        let actions = PersonalActionService(store: store, clock: { Date(timeIntervalSince1970: 10) })
        let paper = topicPaper("2608.30003", topics: [("a", ["a1"]), ("b", ["b1"])])
        try actions.skip(arxivID: paper.arxivId)

        let topicA = SwipeSessionViewModel(
            collection: SwipeCollection(id: "a", title: "A", papers: [paper]),
            store: store
        )
        let topicB = SwipeSessionViewModel(
            collection: SwipeCollection(id: "b", title: "B", papers: [paper]),
            store: store
        )

        XCTAssertNil(topicA.currentPaper)
        XCTAssertNil(topicB.currentPaper)
        XCTAssertEqual(try store.allStates().count, 1)
    }
}

private actor RecordingTopicClient: PublicFeedClientProtocol {
    private var path: String?

    func requestedPath() -> String? { path }
    func fetchFeedIndex() async throws -> FeedIndex { throw URLError(.badServerResponse) }
    func fetchTopicsIndex() async throws -> TopicsIndex { throw URLError(.badServerResponse) }
    func fetchDailyFeed(relativePath: String) async throws -> DailyFeed { throw URLError(.badServerResponse) }
    func fetchTopicFeed(relativePath: String) async throws -> TopicFeed {
        path = relativePath
        return TopicFeed(
            schemaVersion: 1,
            topicId: "runtime",
            subtopicId: nil,
            totalPaperCount: 0,
            days: []
        )
    }
}

private func topicPaper(
    _ id: String,
    topics: [(String, [String])]
) -> PublicPaper {
    PublicPaper(
        arxivId: id,
        title: "Topic Paper \(id)",
        authors: ["Topic Author"],
        abstract: "A complete abstract.",
        arxivUrl: URL(string: "https://arxiv.org/abs/\(id)")!,
        pdfUrl: URL(string: "https://arxiv.org/pdf/\(id)")!,
        firstSeenAt: Date(timeIntervalSince1970: 100),
        categories: ["cs.AI"],
        relevance: 9,
        novelty: 8,
        topicAssignments: topics.map { TopicAssignment(topicId: $0.0, subtopicIds: $0.1) },
        selectionReason: "Relevant",
        tldr: nil,
        bullets: [],
        summaryStatus: .failed,
        heroFigure: nil,
        figureStatus: .notImplemented
    )
}
