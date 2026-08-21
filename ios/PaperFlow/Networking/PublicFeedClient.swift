import Foundation

enum PublicFeedClientError: Error, Equatable {
    case invalidResponse
    case httpStatus(Int)
}

protocol PublicFeedTransport: Sendable {
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse)
}

struct URLSessionPublicFeedTransport: PublicFeedTransport {
    let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else {
            throw PublicFeedClientError.invalidResponse
        }
        return (data, response)
    }
}

struct PublicFeedClient: PublicFeedClientProtocol {
    let publicationRoot: URL
    let transport: any PublicFeedTransport
    let timeout: TimeInterval

    init(
        publicationRoot: URL,
        transport: any PublicFeedTransport = URLSessionPublicFeedTransport(),
        timeout: TimeInterval = 20
    ) throws {
        guard publicationRoot.scheme == "https",
              publicationRoot.absoluteString.hasSuffix("/") else {
            throw PublicContractError.invalidAbsoluteURL
        }
        self.publicationRoot = publicationRoot
        self.transport = transport
        self.timeout = timeout
    }

    func fetchFeedIndex() async throws -> FeedIndex {
        try await fetch(.feedIndex, as: FeedIndex.self).validated()
    }

    func fetchTopicsIndex() async throws -> TopicsIndex {
        try await fetch(.topicsIndex, as: TopicsIndex.self).validated()
    }

    func fetchDailyFeed(relativePath: String) async throws -> DailyFeed {
        try await fetch(.published(relativePath: relativePath), as: DailyFeed.self).validated()
    }

    func fetchTopicFeed(relativePath: String) async throws -> TopicFeed {
        try await fetch(.published(relativePath: relativePath), as: TopicFeed.self).validated()
    }

    private func fetch<Value: Decodable>(
        _ endpoint: PublicFeedEndpoint,
        as type: Value.Type
    ) async throws -> Value {
        try Task.checkCancellation()
        var request = URLRequest(url: try endpoint.url(relativeTo: publicationRoot))
        request.timeoutInterval = timeout
        request.cachePolicy = .reloadRevalidatingCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await transport.data(for: request)
        try Task.checkCancellation()
        guard (200 ... 299).contains(response.statusCode) else {
            throw PublicFeedClientError.httpStatus(response.statusCode)
        }
        let value = try PublicFeedDecoder.decode(type, from: data)
        try Task.checkCancellation()
        return value
    }
}
