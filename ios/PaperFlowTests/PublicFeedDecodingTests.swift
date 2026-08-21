import XCTest
@testable import PaperFlow

final class PublicFeedDecodingTests: XCTestCase {
    func testEveryValidGoldenDecodesAndValidates() throws {
        _ = try decode(FeedIndex.self, "valid/feed_index.json").validated()
        _ = try decode(DailyFeed.self, "valid/daily_feed.json").validated()
        _ = try decode(DailyFeed.self, "valid/zero_day.json").validated()
        _ = try decode(TopicsIndex.self, "valid/topics.json").validated()
        _ = try decode(TopicFeed.self, "valid/topic_feed_all.json").validated()
        _ = try decode(TopicFeed.self, "valid/topic_feed_subtopic.json").validated()
        _ = try decode(PublicPaper.self, "valid/public_paper_generated.json").validated()
        let fallback = try decode(
            PublicPaper.self,
            "valid/public_paper_fallback.json"
        ).validated()
        XCTAssertEqual(fallback.displaySummary, fallback.abstract)
    }

    func testInvalidSchemaCountAndPathGoldensAreRejected() throws {
        XCTAssertThrowsError(
            try decode(DailyFeed.self, "invalid/count_mismatch.json").validated()
        )
        XCTAssertThrowsError(
            try decode(DailyFeed.self, "invalid/schema_version.json").validated()
        )
        XCTAssertThrowsError(
            try decode(TopicsIndex.self, "invalid/unsafe_path.json").validated()
        )
    }

    func testRequiredAbstractAndExplicitFeedURLsRoundTrip() throws {
        let daily = try decode(DailyFeed.self, "valid/daily_feed.json").validated()
        let index = try decode(FeedIndex.self, "valid/feed_index.json").validated()
        let topics = try decode(TopicsIndex.self, "valid/topics.json").validated()

        XCTAssertTrue(daily.papers.allSatisfy { !$0.abstract.isEmpty })
        XCTAssertTrue(index.days.allSatisfy { !$0.feedUrl.isEmpty })
        XCTAssertTrue(topics.topics.allSatisfy { !$0.feedUrl.isEmpty })
        XCTAssertTrue(
            topics.topics.flatMap(\.subtopics).allSatisfy { !$0.feedUrl.isEmpty }
        )
    }

    func testVersionedArxivIdentityNormalizesToOneCanonicalID() {
        XCTAssertEqual(PublicPaper.normalizeArxivID("2608.12345v1"), "2608.12345")
        XCTAssertEqual(PublicPaper.normalizeArxivID("2608.12345v2"), "2608.12345")
        XCTAssertEqual(
            PublicPaper.normalizeArxivID("hep-th/9901001v3"),
            "hep-th/9901001"
        )
    }

    func testPublicationRootResolutionAndUnsafePathRejection() throws {
        let base = try XCTUnwrap(URL(string: "https://example.test/PaperFlow/"))
        XCTAssertEqual(
            try PublicationURLResolver.resolve(
                "data/daily_feeds/2026-08-20.json",
                against: base
            ).absoluteString,
            "https://example.test/PaperFlow/data/daily_feeds/2026-08-20.json"
        )
        for invalid in [
            "/data/feed.json",
            "../feed.json",
            "data\\feed.json",
            "data/feed.json?secret=x",
            "data/feed.json#fragment",
            "https://other.test/feed.json"
        ] {
            XCTAssertThrowsError(
                try PublicationURLResolver.resolve(invalid, against: base)
            )
        }
    }

    func testProjectHasNoCloudKitAnalyticsOrThirdPartyPackages() throws {
        let root = repositoryRoot
        let project = try String(
            contentsOf: root.appendingPathComponent(
                "ios/PaperFlow/PaperFlow.xcodeproj/project.pbxproj"
            ),
            encoding: .utf8
        ).lowercased()
        let swiftFiles = try FileManager.default.subpathsOfDirectory(
            atPath: root.appendingPathComponent("ios/PaperFlow").path
        ).filter {
            $0.hasSuffix(".swift")
                && !$0.contains("Tests/")
                && !$0.contains("UITests/")
        }
        let source = try swiftFiles.map {
            try String(
                contentsOf: root.appendingPathComponent("ios/PaperFlow/\($0)"),
                encoding: .utf8
            )
        }.joined(separator: "\n").lowercased()

        for prohibited in [
            "cloudkit",
            "firebase",
            "import segment",
            "segmentio",
            "mixpanel",
            "packageproductdependency",
            "openrouter_api_key"
        ] {
            XCTAssertFalse(project.contains(prohibited))
            XCTAssertFalse(source.contains(prohibited))
        }
    }

    private func decode<T: Decodable>(_ type: T.Type, _ fixture: String) throws -> T {
        try PublicFeedDecoder.decode(
            type,
            from: Data(contentsOf: contractRoot.appendingPathComponent(fixture))
        )
    }

    private var repositoryRoot: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
    }

    private var contractRoot: URL {
        repositoryRoot.appendingPathComponent("tests/fixtures/contracts/v1")
    }
}
