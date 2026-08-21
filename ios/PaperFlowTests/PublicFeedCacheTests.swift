import XCTest
@testable import PaperFlow

final class PublicFeedCacheTests: XCTestCase {
    private var directory: URL!

    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("PaperFlowCacheTests-\(UUID().uuidString)", isDirectory: true)
    }

    override func tearDownWithError() throws {
        if let directory {
            try? FileManager.default.removeItem(at: directory)
        }
    }

    func testStaleButValidRecordRemainsReadableWithOriginalMetadata() async throws {
        let date = Date(timeIntervalSince1970: 100)
        let payload = Data("valid".utf8)
        let cache = FilePublicFeedCache(directory: directory)

        try await cache.replace(payload, for: .feedIndex, refreshedAt: date)
        let loaded = await cache.value(for: .feedIndex)

        XCTAssertEqual(loaded, CachedPublicFeed(data: payload, lastSuccessfulRefresh: date))
    }

    func testFailedAtomicReplacePreservesPriorRecord() async throws {
        let original = Data("original".utf8)
        let working = FilePublicFeedCache(directory: directory)
        try await working.replace(original, for: .feedIndex, refreshedAt: Date(timeIntervalSince1970: 1))

        let failing = FilePublicFeedCache(
            directory: directory,
            fileSystem: FailingWriteFileSystem()
        )
        do {
            try await failing.replace(
                Data("replacement".utf8),
                for: .feedIndex,
                refreshedAt: Date(timeIntervalSince1970: 2)
            )
            XCTFail("Expected write failure")
        } catch {
            XCTAssertEqual((error as? CocoaError)?.code, .fileWriteUnknown)
        }

        let retained = await working.value(for: .feedIndex)
        XCTAssertEqual(retained?.data, original)
    }

    func testCorruptRecordIsQuarantinedAndNeverPresentedAsEmptyData() async throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let endpoint = PublicFeedEndpoint.feedIndex
        let file = directory.appendingPathComponent(endpoint.cacheKey).appendingPathExtension("json")
        try Data("corrupt".utf8).write(to: file)
        let cache = FilePublicFeedCache(
            directory: directory,
            clock: { Date(timeIntervalSince1970: 123) }
        )

        let corrupted = await cache.value(for: endpoint)
        XCTAssertNil(corrupted)
        let names = try FileManager.default.contentsOfDirectory(atPath: directory.path)
        XCTAssertEqual(names.filter { $0.contains("corrupt-123000") }.count, 1)
        XCTAssertFalse(FileManager.default.fileExists(atPath: file.path))
    }

    func testEndpointRecordsAreIsolated() async throws {
        let cache = FilePublicFeedCache(directory: directory)
        let day = PublicFeedEndpoint.published(relativePath: "data/daily_feeds/2026-08-20.json")
        try await cache.replace(Data("index".utf8), for: .feedIndex, refreshedAt: .distantPast)
        try await cache.replace(Data("day".utf8), for: day, refreshedAt: .distantFuture)

        try await cache.remove(day)

        let index = await cache.value(for: .feedIndex)
        let removedDay = await cache.value(for: day)
        XCTAssertEqual(index?.data, Data("index".utf8))
        XCTAssertNil(removedDay)
    }
}

private struct FailingWriteFileSystem: PublicFeedCacheFileSystem {
    private let base = LocalPublicFeedCacheFileSystem()

    func createDirectory(at url: URL) throws { try base.createDirectory(at: url) }
    func data(at url: URL) throws -> Data { try base.data(at: url) }
    func writeAtomically(_ data: Data, to url: URL) throws {
        throw CocoaError(.fileWriteUnknown)
    }
    func move(_ source: URL, to destination: URL) throws { try base.move(source, to: destination) }
    func remove(_ url: URL) throws { try base.remove(url) }
}
