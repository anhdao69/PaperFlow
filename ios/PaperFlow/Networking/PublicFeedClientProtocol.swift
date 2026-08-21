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
        let topics = try decode("topics", as: TopicsIndex.self).validated()
        let daily = try decode("daily_feed", as: DailyFeed.self).validated()
        for topic in topics.topics {
            if topic.feedUrl == relativePath {
                let papers = daily.papers.filter { paper in
                    paper.topicAssignments.contains { $0.topicId == topic.id }
                }
                return TopicFeed(
                    schemaVersion: 1,
                    topicId: topic.id,
                    subtopicId: nil,
                    totalPaperCount: papers.count,
                    days: papers.isEmpty ? [] : [
                        TopicFeedDay(date: daily.date, paperCount: papers.count, papers: papers)
                    ]
                )
            }
            for subtopic in topic.subtopics where subtopic.feedUrl == relativePath {
                let papers = daily.papers.filter { paper in
                    paper.topicAssignments.contains { assignment in
                        assignment.topicId == topic.id
                            && assignment.subtopicIds.contains(subtopic.id)
                    }
                }
                return TopicFeed(
                    schemaVersion: 1,
                    topicId: topic.id,
                    subtopicId: subtopic.id,
                    totalPaperCount: papers.count,
                    days: papers.isEmpty ? [] : [
                        TopicFeedDay(date: daily.date, paperCount: papers.count, papers: papers)
                    ]
                )
            }
        }
        throw CocoaError(.fileNoSuchFile)
    }

    private func decode<T: Decodable>(_ name: String, as type: T.Type) throws -> T {
        guard let url = Bundle.main.url(forResource: name, withExtension: "json") else {
            throw CocoaError(.fileNoSuchFile)
        }
        return try PublicFeedDecoder.decode(type, from: Data(contentsOf: url))
    }
}
