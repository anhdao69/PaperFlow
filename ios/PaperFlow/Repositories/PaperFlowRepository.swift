import Foundation

enum PublicFeedSource: Equatable, Sendable {
    case network
    case cache
}

struct PublicFeedResult<Value: Sendable>: Sendable {
    let value: Value
    let source: PublicFeedSource
    let lastSuccessfulRefresh: Date
    let refreshErrorDescription: String?
}

enum PaperFlowRepositoryError: Error, Equatable {
    case unavailable(String)
}

actor PaperFlowRepository {
    private let client: any PublicFeedClientProtocol
    private let cache: any PublicFeedCache
    private let clock: @Sendable () -> Date

    private var indexTask: Task<PublicFeedResult<FeedIndex>, Error>?
    private var topicsTask: Task<PublicFeedResult<TopicsIndex>, Error>?
    private var dailyTasks: [String: Task<PublicFeedResult<DailyFeed>, Error>] = [:]
    private var topicTasks: [String: Task<PublicFeedResult<TopicFeed>, Error>] = [:]

    init(
        client: any PublicFeedClientProtocol,
        cache: any PublicFeedCache,
        clock: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.client = client
        self.cache = cache
        self.clock = clock
    }

    func feedIndex() async throws -> PublicFeedResult<FeedIndex> {
        if let indexTask { return try await indexTask.value }
        let task = makeTask(
            endpoint: .feedIndex,
            fetch: { try await self.client.fetchFeedIndex().validated() },
            validateCached: { try $0.validated() }
        )
        indexTask = task
        do {
            let result = try await task.value
            indexTask = nil
            return result
        } catch {
            indexTask = nil
            throw error
        }
    }

    func topicsIndex() async throws -> PublicFeedResult<TopicsIndex> {
        if let topicsTask { return try await topicsTask.value }
        let task = makeTask(
            endpoint: .topicsIndex,
            fetch: { try await self.client.fetchTopicsIndex().validated() },
            validateCached: { try $0.validated() }
        )
        topicsTask = task
        do {
            let result = try await task.value
            topicsTask = nil
            return result
        } catch {
            topicsTask = nil
            throw error
        }
    }

    func dailyFeed(relativePath: String) async throws -> PublicFeedResult<DailyFeed> {
        _ = try PublicationURLResolver.validateRelativePath(relativePath)
        if let task = dailyTasks[relativePath] { return try await task.value }
        let task = makeTask(
            endpoint: .published(relativePath: relativePath),
            fetch: { try await self.client.fetchDailyFeed(relativePath: relativePath).validated() },
            validateCached: { try $0.validated() }
        )
        dailyTasks[relativePath] = task
        do {
            let result = try await task.value
            dailyTasks[relativePath] = nil
            return result
        } catch {
            dailyTasks[relativePath] = nil
            throw error
        }
    }

    func topicFeed(relativePath: String) async throws -> PublicFeedResult<TopicFeed> {
        _ = try PublicationURLResolver.validateRelativePath(relativePath)
        if let task = topicTasks[relativePath] { return try await task.value }
        let task = makeTask(
            endpoint: .published(relativePath: relativePath),
            fetch: { try await self.client.fetchTopicFeed(relativePath: relativePath).validated() },
            validateCached: { try $0.validated() }
        )
        topicTasks[relativePath] = task
        do {
            let result = try await task.value
            topicTasks[relativePath] = nil
            return result
        } catch {
            topicTasks[relativePath] = nil
            throw error
        }
    }

    func removeCachedPublicFeed(relativePath: String) async throws {
        _ = try PublicationURLResolver.validateRelativePath(relativePath)
        try await cache.remove(.published(relativePath: relativePath))
    }

    private func makeTask<Value: Codable & Sendable>(
        endpoint: PublicFeedEndpoint,
        fetch: @escaping @Sendable () async throws -> Value,
        validateCached: @escaping @Sendable (Value) throws -> Value
    ) -> Task<PublicFeedResult<Value>, Error> {
        let cache = cache
        let clock = clock
        return Task {
            do {
                let value = try await fetch()
                try Task.checkCancellation()
                let refreshedAt = clock()
                try await cache.replace(
                    try PublicFeedEncoder.encode(value),
                    for: endpoint,
                    refreshedAt: refreshedAt
                )
                try Task.checkCancellation()
                return PublicFeedResult(
                    value: value,
                    source: .network,
                    lastSuccessfulRefresh: refreshedAt,
                    refreshErrorDescription: nil
                )
            } catch is CancellationError {
                throw CancellationError()
            } catch {
                guard let cached = await cache.value(for: endpoint) else {
                    throw PaperFlowRepositoryError.unavailable(
                        "PaperFlow public data is unavailable and no cached copy exists."
                    )
                }
                do {
                    let value = try PublicFeedDecoder.decode(Value.self, from: cached.data)
                    let validated = try validateCached(value)
                    return PublicFeedResult(
                        value: validated,
                        source: .cache,
                        lastSuccessfulRefresh: cached.lastSuccessfulRefresh,
                        refreshErrorDescription: "The latest refresh failed. Showing saved public data."
                    )
                } catch {
                    await cache.quarantine(endpoint)
                    throw PaperFlowRepositoryError.unavailable(
                        "PaperFlow public data is unavailable and the cached copy is invalid."
                    )
                }
            }
        }
    }

}
