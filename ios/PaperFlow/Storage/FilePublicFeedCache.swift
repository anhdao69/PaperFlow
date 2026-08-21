import Foundation

actor FilePublicFeedCache: PublicFeedCache {
    private struct Record: Codable {
        let relativePath: String
        let lastSuccessfulRefresh: Date
        let payload: Data
    }

    private let directory: URL
    private let fileSystem: any PublicFeedCacheFileSystem
    private let clock: @Sendable () -> Date

    init(
        directory: URL,
        fileSystem: any PublicFeedCacheFileSystem = LocalPublicFeedCacheFileSystem(),
        clock: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.directory = directory
        self.fileSystem = fileSystem
        self.clock = clock
    }

    func value(for endpoint: PublicFeedEndpoint) async -> CachedPublicFeed? {
        let url = fileURL(for: endpoint)
        do {
            let data = try fileSystem.data(at: url)
            let record = try decoder.decode(Record.self, from: data)
            guard record.relativePath == endpoint.relativePath else {
                throw CocoaError(.fileReadCorruptFile)
            }
            return CachedPublicFeed(
                data: record.payload,
                lastSuccessfulRefresh: record.lastSuccessfulRefresh
            )
        } catch CocoaError.fileReadNoSuchFile {
            return nil
        } catch {
            quarantineFile(at: url)
            return nil
        }
    }

    func replace(
        _ data: Data,
        for endpoint: PublicFeedEndpoint,
        refreshedAt: Date
    ) async throws {
        try fileSystem.createDirectory(at: directory)
        let record = Record(
            relativePath: endpoint.relativePath,
            lastSuccessfulRefresh: refreshedAt,
            payload: data
        )
        try fileSystem.writeAtomically(try encoder.encode(record), to: fileURL(for: endpoint))
    }

    func quarantine(_ endpoint: PublicFeedEndpoint) async {
        quarantineFile(at: fileURL(for: endpoint))
    }

    func remove(_ endpoint: PublicFeedEndpoint) async throws {
        try fileSystem.remove(fileURL(for: endpoint))
    }

    private func quarantineFile(at url: URL) {
        let milliseconds = Int(clock().timeIntervalSince1970 * 1_000)
        let quarantineURL = url.appendingPathExtension("corrupt-\(milliseconds)")
        try? fileSystem.createDirectory(at: directory)
        try? fileSystem.move(url, to: quarantineURL)
    }

    private func fileURL(for endpoint: PublicFeedEndpoint) -> URL {
        directory.appendingPathComponent(endpoint.cacheKey).appendingPathExtension("json")
    }

    private var encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }

    private var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
