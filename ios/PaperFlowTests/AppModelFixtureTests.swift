import XCTest
@testable import PaperFlow

@MainActor
final class AppModelFixtureTests: XCTestCase {
    func testBundledFixtureLoadsWithoutNetwork() async {
        let model = AppModel(client: InMemoryFeedClient())

        await model.loadFixtureShellIfNeeded()

        XCTAssertEqual(model.loadState, .loaded)
        XCTAssertEqual(model.feedIndex?.dayCount, 1)
        XCTAssertEqual(model.topicsIndex?.topics.count, 1)
        XCTAssertEqual(model.dailyFeed?.paperCount, 0)
    }
}

private struct InMemoryFeedClient: PublicFeedClientProtocol {
    private enum FixtureError: Error {
        case unexpectedDailyFeedPath(String)
    }

    func fetchFeedIndex() async throws -> FeedIndex {
        try decode(
            FeedIndex.self,
            #"{"schema_version":1,"generated_at":"2026-08-20T21:05:00-04:00","timezone":"America/New_York","total_paper_count":0,"day_count":1,"days":[{"date":"2026-08-20","paper_count":0,"feed_url":"data/daily_feeds/2026-08-20.json"}]}"#
        )
    }

    func fetchTopicsIndex() async throws -> TopicsIndex {
        try decode(
            TopicsIndex.self,
            #"{"schema_version":1,"taxonomy_version":1,"total_paper_count":0,"topics":[{"id":"world-models","name":"World Models","paper_count":0,"feed_url":"data/topic_feeds/world-models/all.json","subtopics":[]}]}"#
        )
    }

    func fetchDailyFeed(relativePath: String) async throws -> DailyFeed {
        guard relativePath == "data/daily_feeds/2026-08-20.json" else {
            throw FixtureError.unexpectedDailyFeedPath(relativePath)
        }
        return try decode(
            DailyFeed.self,
            #"{"schema_version":1,"date":"2026-08-20","paper_count":0,"papers":[]}"#
        )
    }

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try PublicFeedDecoder.decode(type, from: Data(json.utf8))
    }
}
