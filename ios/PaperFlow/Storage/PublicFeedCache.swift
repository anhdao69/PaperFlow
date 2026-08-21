import Foundation

struct CachedPublicFeed: Equatable, Sendable {
    let data: Data
    let lastSuccessfulRefresh: Date
}

protocol PublicFeedCache: Sendable {
    func value(for endpoint: PublicFeedEndpoint) async -> CachedPublicFeed?
    func replace(
        _ data: Data,
        for endpoint: PublicFeedEndpoint,
        refreshedAt: Date
    ) async throws
    func quarantine(_ endpoint: PublicFeedEndpoint) async
    func remove(_ endpoint: PublicFeedEndpoint) async throws
}

protocol PublicFeedCacheFileSystem: Sendable {
    func createDirectory(at url: URL) throws
    func data(at url: URL) throws -> Data
    func writeAtomically(_ data: Data, to url: URL) throws
    func move(_ source: URL, to destination: URL) throws
    func remove(_ url: URL) throws
}

struct LocalPublicFeedCacheFileSystem: PublicFeedCacheFileSystem {
    func createDirectory(at url: URL) throws {
        try FileManager.default.createDirectory(
            at: url,
            withIntermediateDirectories: true
        )
    }

    func data(at url: URL) throws -> Data {
        try Data(contentsOf: url)
    }

    func writeAtomically(_ data: Data, to url: URL) throws {
        try data.write(to: url, options: .atomic)
    }

    func move(_ source: URL, to destination: URL) throws {
        try FileManager.default.moveItem(at: source, to: destination)
    }

    func remove(_ url: URL) throws {
        guard FileManager.default.fileExists(atPath: url.path) else { return }
        try FileManager.default.removeItem(at: url)
    }
}
