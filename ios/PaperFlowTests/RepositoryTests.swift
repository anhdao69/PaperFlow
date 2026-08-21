import SwiftData
import XCTest
@testable import PaperFlow

final class RepositoryTests: XCTestCase {
    func testOnlineThenInvalidThenOfflineAlwaysServesLastValidFeed() async throws {
        let client = SequencedFeedClient()
        let cache = MemoryPublicFeedCache()
        let repository = PaperFlowRepository(
            client: client,
            cache: cache,
            clock: { Date(timeIntervalSince1970: 500) }
        )

        await client.setDailyModes([.valid, .invalidCount, .offline])
        let online = try await repository.dailyFeed(relativePath: dayPath)
        let invalidFallback = try await repository.dailyFeed(relativePath: dayPath)
        let offlineFallback = try await repository.dailyFeed(relativePath: dayPath)

        XCTAssertEqual(online.source, .network)
        XCTAssertEqual(invalidFallback.source, .cache)
        XCTAssertEqual(offlineFallback.source, .cache)
        XCTAssertEqual(online.value, invalidFallback.value)
        XCTAssertEqual(online.value, offlineFallback.value)
        XCTAssertEqual(invalidFallback.lastSuccessfulRefresh, Date(timeIntervalSince1970: 500))
        XCTAssertNotNil(invalidFallback.refreshErrorDescription)
    }

    func testInvalidFirstPayloadDoesNotCreateCacheOrSuccessMetadata() async throws {
        let client = SequencedFeedClient()
        await client.setDailyModes([.invalidCount])
        let cache = MemoryPublicFeedCache()
        let repository = PaperFlowRepository(client: client, cache: cache)

        do {
            _ = try await repository.dailyFeed(relativePath: dayPath)
            XCTFail("Expected unavailable result")
        } catch {
            XCTAssertNotNil(error as? PaperFlowRepositoryError)
        }
        let cached = await cache.value(for: .published(relativePath: dayPath))
        XCTAssertNil(cached)
    }

    func testConcurrentRequestsAreCoalescedIntoOneFetchAndCacheWrite() async throws {
        let client = SequencedFeedClient(delayNanoseconds: 50_000_000)
        await client.setDailyModes([.valid])
        let cache = MemoryPublicFeedCache()
        let repository = PaperFlowRepository(client: client, cache: cache)

        async let first = repository.dailyFeed(relativePath: dayPath)
        async let second = repository.dailyFeed(relativePath: dayPath)
        _ = try await (first, second)

        let requestCount = await client.dailyRequestCount()
        let writeCount = await cache.replaceCount()
        XCTAssertEqual(requestCount, 1)
        XCTAssertEqual(writeCount, 1)
    }

    @MainActor
    func testPublicCacheRemovalAndFailedRefreshDoNotTouchPersonalSwiftData() async throws {
        let container = try ModelContainer(
            for: PersonalPaperState.self,
            SavedPaperSnapshot.self,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        let actions = PersonalActionService(store: store, clock: { Date(timeIntervalSince1970: 10) })
        let paper = makePaper()
        try actions.save(paper)

        let client = SequencedFeedClient()
        await client.setDailyModes([.valid, .offline])
        let cache = MemoryPublicFeedCache()
        let repository = PaperFlowRepository(client: client, cache: cache)
        _ = try await repository.dailyFeed(relativePath: dayPath)
        try await repository.removeCachedPublicFeed(relativePath: dayPath)
        do {
            _ = try await repository.dailyFeed(relativePath: dayPath)
            XCTFail("Expected offline/no-cache failure")
        } catch {}

        let personal = try XCTUnwrap(store.state(for: paper.arxivId))
        XCTAssertTrue(personal.saved)
        XCTAssertEqual(personal.snapshot?.title, paper.title)
    }
}

private let dayPath = "data/daily_feeds/2026-08-20.json"

private actor MemoryPublicFeedCache: PublicFeedCache {
    private var values: [PublicFeedEndpoint: CachedPublicFeed] = [:]
    private var writes = 0

    func value(for endpoint: PublicFeedEndpoint) -> CachedPublicFeed? { values[endpoint] }
    func replace(_ data: Data, for endpoint: PublicFeedEndpoint, refreshedAt: Date) {
        writes += 1
        values[endpoint] = CachedPublicFeed(data: data, lastSuccessfulRefresh: refreshedAt)
    }
    func quarantine(_ endpoint: PublicFeedEndpoint) { values[endpoint] = nil }
    func remove(_ endpoint: PublicFeedEndpoint) { values[endpoint] = nil }
    func replaceCount() -> Int { writes }
}

private actor SequencedFeedClient: PublicFeedClientProtocol {
    enum Mode { case valid, invalidCount, offline }

    private var dailyModes: [Mode] = []
    private var dailyRequests = 0
    private let delayNanoseconds: UInt64

    init(delayNanoseconds: UInt64 = 0) {
        self.delayNanoseconds = delayNanoseconds
    }

    func setDailyModes(_ modes: [Mode]) { dailyModes = modes }
    func dailyRequestCount() -> Int { dailyRequests }

    func fetchFeedIndex() async throws -> FeedIndex { makeFeedIndex() }
    func fetchTopicsIndex() async throws -> TopicsIndex { makeTopicsIndex() }

    func fetchDailyFeed(relativePath: String) async throws -> DailyFeed {
        dailyRequests += 1
        if delayNanoseconds > 0 { try await Task.sleep(nanoseconds: delayNanoseconds) }
        guard !dailyModes.isEmpty else { throw URLError(.notConnectedToInternet) }
        switch dailyModes.removeFirst() {
        case .valid:
            return makeDailyFeed()
        case .invalidCount:
            return DailyFeed(schemaVersion: 1, date: testDate, paperCount: 2, papers: [makePaper()])
        case .offline:
            throw URLError(.notConnectedToInternet)
        }
    }

    func fetchTopicFeed(relativePath: String) async throws -> TopicFeed {
        throw URLError(.notConnectedToInternet)
    }
}

private func makeFeedIndex() -> FeedIndex {
    FeedIndex(
        schemaVersion: 1,
        generatedAt: testDate,
        timezone: "America/New_York",
        totalPaperCount: 1,
        dayCount: 1,
        days: [FeedDay(date: testDate, paperCount: 1, feedUrl: dayPath)]
    )
}

private func makeTopicsIndex() -> TopicsIndex {
    TopicsIndex(schemaVersion: 1, taxonomyVersion: 1, totalPaperCount: 1, topics: [])
}

private func makeDailyFeed() -> DailyFeed {
    DailyFeed(schemaVersion: 1, date: testDate, paperCount: 1, papers: [makePaper()])
}

private let testDate = Date(timeIntervalSince1970: 1_776_902_400)

private func makePaper() -> PublicPaper {
    PublicPaper(
        arxivId: "2608.12345",
        title: "Cached Paper",
        authors: ["A. Author"],
        abstract: "An offline-safe abstract.",
        arxivUrl: URL(string: "https://arxiv.org/abs/2608.12345")!,
        pdfUrl: URL(string: "https://arxiv.org/pdf/2608.12345")!,
        firstSeenAt: testDate,
        categories: ["cs.AI"],
        relevance: 9,
        novelty: 8,
        topicAssignments: [],
        selectionReason: "Relevant",
        tldr: nil,
        bullets: [],
        summaryStatus: .failed,
        heroFigure: nil,
        figureStatus: .notImplemented
    )
}
