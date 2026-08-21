import Foundation

protocol PublicFeedClientProtocol: Sendable {
    func fetchFeedIndex() async throws -> FeedIndex
    func fetchTopicsIndex() async throws -> TopicsIndex
    func fetchDailyFeed(relativePath: String) async throws -> DailyFeed
    func fetchTopicFeed(relativePath: String) async throws -> TopicFeed
}

struct BundledFixtureFeedClient: PublicFeedClientProtocol {
    func fetchFeedIndex() async throws -> FeedIndex {
        try decode("feed_index", as: FeedIndex.self)
    }

    func fetchTopicsIndex() async throws -> TopicsIndex {
        try decode("topics", as: TopicsIndex.self)
    }

    func fetchDailyFeed(relativePath: String) async throws -> DailyFeed {
        _ = try PublicationURLResolver.validateRelativePath(relativePath)
        return try decode("daily_feed", as: DailyFeed.self)
    }

    func fetchTopicFeed(relativePath: String) async throws -> TopicFeed {
        _ = try PublicationURLResolver.validateRelativePath(relativePath)
        return try decode("topic_feed", as: TopicFeed.self)
    }

    private func decode<T: Decodable>(_ name: String, as type: T.Type) throws -> T {
        guard let url = Bundle.main.url(forResource: name, withExtension: "json") else {
            throw CocoaError(.fileNoSuchFile)
        }
        return try PublicFeedDecoder.decode(type, from: Data(contentsOf: url))
    }
}
