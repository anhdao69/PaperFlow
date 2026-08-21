import XCTest
@testable import PaperFlow

final class PublicFeedClientTests: XCTestCase {
    func testEndpointsUseConfiguredPublicationRootAndExplicitPaths() async throws {
        let recorder = RequestRecorder(responseData: Data(validFeedIndexJSON.utf8))
        let client = try PublicFeedClient(
            publicationRoot: XCTUnwrap(URL(string: "https://example.test/PaperFlow/")),
            transport: recorder,
            timeout: 7
        )

        _ = try await client.fetchFeedIndex()

        let recordedRequest = await recorder.lastRequest()
        let request = try XCTUnwrap(recordedRequest)
        XCTAssertEqual(
            request.url?.absoluteString,
            "https://example.test/PaperFlow/data/feed_index.json"
        )
        XCTAssertEqual(request.timeoutInterval, 7, accuracy: 0.01)
        XCTAssertEqual(request.value(forHTTPHeaderField: "Accept"), "application/json")
    }

    func testNonSuccessStatusIsRejected() async throws {
        let client = try makeClient(statusCode: 503, data: Data())
        do {
            _ = try await client.fetchFeedIndex()
            XCTFail("Expected a status error")
        } catch {
            XCTAssertEqual(error as? PublicFeedClientError, .httpStatus(503))
        }
    }

    func testInvalidJSONSchemaAndCountAreRejected() async throws {
        let invalidPayloads = [
            Data("not json".utf8),
            Data(validFeedIndexJSON.replacingOccurrences(of: #""schema_version":1"#, with: #""schema_version":2"#).utf8),
            Data(validFeedIndexJSON.replacingOccurrences(of: #""day_count":1"#, with: #""day_count":2"#).utf8)
        ]

        for payload in invalidPayloads {
            let client = try makeClient(statusCode: 200, data: payload)
            do {
                _ = try await client.fetchFeedIndex()
                XCTFail("Expected invalid public data")
            } catch {
                XCTAssertFalse(error is CancellationError)
            }
        }
    }

    func testTransportTimeoutPropagates() async throws {
        let client = try PublicFeedClient(
            publicationRoot: XCTUnwrap(URL(string: "https://example.test/PaperFlow/")),
            transport: ClosureTransport { _ in
                throw URLError(.timedOut)
            }
        )

        do {
            _ = try await client.fetchFeedIndex()
            XCTFail("Expected timeout")
        } catch {
            XCTAssertEqual((error as? URLError)?.code, .timedOut)
        }
    }

    func testCancellationDoesNotReturnDecodedValue() async throws {
        let transport = BlockingTransport()
        let client = try PublicFeedClient(
            publicationRoot: XCTUnwrap(URL(string: "https://example.test/PaperFlow/")),
            transport: transport
        )
        let task = Task { try await client.fetchFeedIndex() }

        await transport.waitUntilRequested()
        task.cancel()
        await transport.resume(with: Data(validFeedIndexJSON.utf8))

        do {
            _ = try await task.value
            XCTFail("Expected cancellation")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
    }

    func testUnsafeRelativeEndpointIsRejectedBeforeTransport() async throws {
        let recorder = RequestRecorder(responseData: Data())
        let client = try PublicFeedClient(
            publicationRoot: XCTUnwrap(URL(string: "https://example.test/PaperFlow/")),
            transport: recorder
        )

        do {
            _ = try await client.fetchDailyFeed(relativePath: "../private.json")
            XCTFail("Expected path rejection")
        } catch {
            XCTAssertEqual(error as? PublicContractError, .invalidRelativePath)
        }
        let request = await recorder.lastRequest()
        XCTAssertNil(request)
    }

    private func makeClient(statusCode: Int, data: Data) throws -> PublicFeedClient {
        try PublicFeedClient(
            publicationRoot: XCTUnwrap(URL(string: "https://example.test/PaperFlow/")),
            transport: ClosureTransport { request in
                let response = HTTPURLResponse(
                    url: try XCTUnwrap(request.url),
                    statusCode: statusCode,
                    httpVersion: nil,
                    headerFields: nil
                )!
                return (data, response)
            }
        )
    }
}

private let validFeedIndexJSON = #"{"schema_version":1,"generated_at":"2026-08-20T21:05:00Z","timezone":"America/New_York","total_paper_count":0,"day_count":1,"days":[{"date":"2026-08-20","paper_count":0,"feed_url":"data/daily_feeds/2026-08-20.json"}]}"#

private struct ClosureTransport: PublicFeedTransport {
    let operation: @Sendable (URLRequest) async throws -> (Data, HTTPURLResponse)

    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        try await operation(request)
    }
}

private actor RequestRecorder: PublicFeedTransport {
    private var request: URLRequest?
    private let responseData: Data

    init(responseData: Data) {
        self.responseData = responseData
    }

    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        self.request = request
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        return (responseData, response)
    }

    func lastRequest() -> URLRequest? { request }
}

private actor BlockingTransport: PublicFeedTransport {
    private var continuation: CheckedContinuation<Void, Never>?
    private var responseContinuation: CheckedContinuation<Data, Never>?
    private var requested = false

    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        requested = true
        continuation?.resume()
        continuation = nil
        let data = await withCheckedContinuation { responseContinuation = $0 }
        return (
            data,
            HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: nil,
                headerFields: nil
            )!
        )
    }

    func waitUntilRequested() async {
        guard !requested else { return }
        await withCheckedContinuation { continuation = $0 }
    }

    func resume(with data: Data) {
        responseContinuation?.resume(returning: data)
        responseContinuation = nil
    }
}
