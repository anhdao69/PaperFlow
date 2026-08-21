import Foundation

enum PublicFeedEndpoint: Hashable, Sendable {
    case feedIndex
    case topicsIndex
    case published(relativePath: String)

    var relativePath: String {
        switch self {
        case .feedIndex:
            "data/feed_index.json"
        case .topicsIndex:
            "data/topics.json"
        case let .published(relativePath):
            relativePath
        }
    }

    func url(relativeTo publicationRoot: URL) throws -> URL {
        try PublicationURLResolver.resolve(relativePath, against: publicationRoot)
    }

    var cacheKey: String {
        relativePath.utf8.map { String(format: "%02x", $0) }.joined()
    }
}
