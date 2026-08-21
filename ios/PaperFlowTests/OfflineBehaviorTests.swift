import SwiftData
import XCTest
@testable import PaperFlow

@MainActor
final class OfflineBehaviorTests: XCTestCase {
    func testCachedLaunchSurfacesOfflineMetadataWithoutDiscardingContent() async {
        let model = AppModel(
            client: BundledFixtureFeedClient(),
            clock: { Date(timeIntervalSince1970: 50) },
            reportsCachedData: true
        )

        await model.loadFixtureShellIfNeeded()

        XCTAssertEqual(model.loadState, .loaded)
        XCTAssertTrue(model.isShowingCachedData)
        XCTAssertNotNil(model.refreshMessage)
        XCTAssertEqual(model.dailyFeed?.paperCount, 2)
        XCTAssertNotNil(model.lastUpdatedAt)
    }

    func testFailedRefreshPreservesPreviouslyLoadedPublicContent() async {
        let source = SwitchableFixtureSource()
        let model = AppModel(source: source, clock: { Date(timeIntervalSince1970: 50) })
        await model.loadFixtureShellIfNeeded()
        let originalIndex = model.feedIndex
        let originalFeed = model.dailyFeed
        await source.setOffline(true)

        await model.refresh()

        XCTAssertEqual(model.loadState, .loaded)
        XCTAssertEqual(model.feedIndex, originalIndex)
        XCTAssertEqual(model.dailyFeed, originalFeed)
        XCTAssertTrue(model.isShowingCachedData)
        XCTAssertNotNil(model.refreshMessage)
    }

    func testNoCacheOfflineIsRetryableErrorRatherThanValidEmpty() async {
        let source = SwitchableFixtureSource(offline: true)
        let model = AppModel(source: source)

        await model.loadFixtureShellIfNeeded()

        guard case let .failed(message) = model.loadState else {
            return XCTFail("Expected an unavailable state")
        }
        XCTAssertTrue(message.contains("try again"))
        XCTAssertNil(model.feedIndex)
    }

    func testValidZeroFeedLoadsAsEmptyAndIsNotAnError() async {
        let model = AppModel(source: ZeroFeedSource())

        await model.loadFixtureShellIfNeeded()

        XCTAssertEqual(model.loadState, .loaded)
        XCTAssertEqual(model.feedIndex?.totalPaperCount, 0)
        XCTAssertNil(model.dailyFeed)
        XCTAssertNil(model.refreshMessage)
    }

    func testPersonalMutationsRemainIndependentWhilePublicSourceIsOffline() async throws {
        let model = AppModel(
            client: BundledFixtureFeedClient(),
            reportsCachedData: true
        )
        await model.loadFixtureShellIfNeeded()
        let paper = try XCTUnwrap(model.dailyFeed?.papers.first)
        let container = try ModelContainer(
            for: PersonalPaperState.self,
            SavedPaperSnapshot.self,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        let actions = PersonalActionService(store: store, clock: { Date(timeIntervalSince1970: 90) })

        let state = try actions.save(paper)
        try actions.transition(arxivID: paper.arxivId, to: .reading)
        try actions.updateNote(arxivID: paper.arxivId, note: "Offline note")
        try actions.updateRating(arxivID: paper.arxivId, rating: 5)

        XCTAssertTrue(state.saved)
        XCTAssertEqual(state.readingStatus, .reading)
        XCTAssertEqual(state.note, "Offline note")
        XCTAssertEqual(state.rating, 5)
        XCTAssertNotNil(state.snapshot?.publicPaper())
    }
}

private actor SwitchableFixtureSource: PaperFlowDataSource {
    private var offline: Bool
    private let client = BundledFixtureFeedClient()

    init(offline: Bool = false) { self.offline = offline }

    func setOffline(_ value: Bool) { offline = value }

    func feedIndex() async throws -> PublicFeedResult<FeedIndex> {
        try available(try await client.fetchFeedIndex().validated())
    }

    func topicsIndex() async throws -> PublicFeedResult<TopicsIndex> {
        try available(try await client.fetchTopicsIndex().validated())
    }

    func dailyFeed(relativePath: String) async throws -> PublicFeedResult<DailyFeed> {
        try available(try await client.fetchDailyFeed(relativePath: relativePath).validated())
    }

    func topicFeed(relativePath: String) async throws -> PublicFeedResult<TopicFeed> {
        try available(try await client.fetchTopicFeed(relativePath: relativePath).validated())
    }

    private func available<Value: Sendable>(_ value: Value) throws -> PublicFeedResult<Value> {
        guard !offline else { throw URLError(.notConnectedToInternet) }
        return PublicFeedResult(
            value: value,
            source: .network,
            lastSuccessfulRefresh: Date(timeIntervalSince1970: 10),
            refreshErrorDescription: nil
        )
    }
}

private actor ZeroFeedSource: PaperFlowDataSource {
    private let refreshedAt = Date(timeIntervalSince1970: 10)

    func feedIndex() async throws -> PublicFeedResult<FeedIndex> {
        result(FeedIndex(
            schemaVersion: 1,
            generatedAt: refreshedAt,
            timezone: "America/New_York",
            totalPaperCount: 0,
            dayCount: 0,
            days: []
        ))
    }

    func topicsIndex() async throws -> PublicFeedResult<TopicsIndex> {
        result(TopicsIndex(
            schemaVersion: 1,
            taxonomyVersion: 1,
            totalPaperCount: 0,
            topics: []
        ))
    }

    func dailyFeed(relativePath: String) async throws -> PublicFeedResult<DailyFeed> {
        throw CocoaError(.fileNoSuchFile)
    }

    func topicFeed(relativePath: String) async throws -> PublicFeedResult<TopicFeed> {
        throw CocoaError(.fileNoSuchFile)
    }

    private func result<Value: Sendable>(_ value: Value) -> PublicFeedResult<Value> {
        PublicFeedResult(
            value: value,
            source: .network,
            lastSuccessfulRefresh: refreshedAt,
            refreshErrorDescription: nil
        )
    }
}
