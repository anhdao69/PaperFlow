import XCTest
@testable import PaperFlow

@MainActor
final class SavedViewModelTests: XCTestCase {
    func testCountsFilterUnsavedAndDeduplicateCanonicalIDs() {
        let queue = state("2608.50001", status: .queue)
        let duplicate = state("2608.50001", status: .queue)
        let reading = state("2608.50002", status: .reading)
        let done = state("2608.50003", status: .done)
        let unsaved = state("2608.50004", status: .queue, saved: false)

        let counts = SavedViewModel.counts([queue, duplicate, reading, done, unsaved])

        XCTAssertEqual(counts, SavedCounts(queue: 1, reading: 1, done: 1))
        XCTAssertEqual(counts.total, 3)
    }

    func testSearchIsCaseAndDiacriticInsensitiveAcrossEveryRequiredField() {
        let item = state(
            "2608.50005",
            status: .queue,
            title: "Résumé Agents",
            author: "Zoë Researcher",
            summary: "Café-scale embodied reasoning",
            topicID: "world-models",
            subtopicID: "video-world-models"
        )
        item.note = "Re-read the naïve baseline"
        let topics = topicIndex()

        for query in ["RESUME", "zoe", "cafe", "WORLD MODELS", "video world", "NAIVE"] {
            XCTAssertEqual(
                SavedViewModel.records([item], status: .queue, query: query, topics: topics).count,
                1,
                "Expected Saved search to match \(query)"
            )
        }
        XCTAssertTrue(SavedViewModel.records([item], status: .queue, query: "missing", topics: topics).isEmpty)
    }

    func testQueueSortsUseStoredFieldsAndDeterministicTieBreakers() {
        let alpha = state("2608.50010", status: .queue, title: "Alpha", relevance: 7, novelty: 10)
        alpha.savedAt = date(1)
        alpha.lastSavedAt = date(5)
        let beta = state("2608.50011", status: .queue, title: "Beta", relevance: 10, novelty: 6)
        beta.savedAt = date(2)
        beta.lastSavedAt = date(4)

        XCTAssertEqual(ids([alpha, beta], .recentlySaved), [alpha.canonicalArxivID, beta.canonicalArxivID])
        XCTAssertEqual(ids([alpha, beta], .oldestSaved), [alpha.canonicalArxivID, beta.canonicalArxivID])
        XCTAssertEqual(ids([alpha, beta], .relevance), [beta.canonicalArxivID, alpha.canonicalArxivID])
        XCTAssertEqual(ids([alpha, beta], .novelty), [alpha.canonicalArxivID, beta.canonicalArxivID])
        XCTAssertEqual(ids([beta, alpha], .title), [alpha.canonicalArxivID, beta.canonicalArxivID])
    }

    func testReadingSortUsesLastOpenedThenStatusThenLastSaveFallback() {
        let opened = state("2608.50020", status: .reading, title: "Opened")
        opened.lastOpenedAt = date(10)
        let transitioned = state("2608.50021", status: .reading, title: "Transitioned")
        transitioned.statusChangedAt = date(9)
        let saved = state("2608.50022", status: .reading, title: "Saved")
        saved.lastSavedAt = date(8)

        XCTAssertEqual(
            ids([saved, transitioned, opened], .lastOpened, status: .reading),
            [opened.canonicalArxivID, transitioned.canonicalArxivID, saved.canonicalArxivID]
        )
    }

    func testDoneSortsUseCompletionTimestamp() {
        let older = state("2608.50030", status: .done, title: "Older")
        older.completedAt = date(3)
        let newer = state("2608.50031", status: .done, title: "Newer")
        newer.completedAt = date(6)

        XCTAssertEqual(
            ids([older, newer], .recentlyCompleted, status: .done),
            [newer.canonicalArxivID, older.canonicalArxivID]
        )
        XCTAssertEqual(
            ids([newer, older], .oldestCompleted, status: .done),
            [older.canonicalArxivID, newer.canonicalArxivID]
        )
    }

    func testRetainedSnapshotReconstructsDetailWithoutAnyPublicCache() throws {
        let item = state(
            "2608.50040",
            status: .reading,
            title: "Offline Detail",
            summary: "A retained display summary",
            topicID: "world-models",
            subtopicID: "video-world-models"
        )
        item.note = "Private field"
        item.rating = 5
        let snapshot = try XCTUnwrap(item.snapshot)

        let reconstructed = snapshot.publicPaper()

        XCTAssertEqual(reconstructed.arxivId, item.canonicalArxivID)
        XCTAssertEqual(reconstructed.title, "Offline Detail")
        XCTAssertEqual(reconstructed.displaySummary, "A retained display summary")
        XCTAssertEqual(reconstructed.topicAssignments.first?.subtopicIds, ["video-world-models"])
        XCTAssertEqual(item.note, "Private field")
        XCTAssertEqual(item.rating, 5)
    }

    private func ids(
        _ states: [PersonalPaperState],
        _ sort: SavedSort,
        status: ReadingStatus = .queue
    ) -> [String] {
        SavedViewModel.records(states, status: status, sort: sort).map(\.canonicalArxivID)
    }

    private func state(
        _ id: String,
        status: ReadingStatus,
        saved: Bool = true,
        title: String = "Fixture",
        author: String = "Fixture Author",
        summary: String = "Fixture summary",
        topicID: String = "topic",
        subtopicID: String = "subtopic",
        relevance: Int = 8,
        novelty: Int = 7
    ) -> PersonalPaperState {
        let paper = PublicPaper(
            arxivId: id,
            title: title,
            authors: [author],
            abstract: "Fixture abstract",
            arxivUrl: URL(string: "https://arxiv.org/abs/\(id)")!,
            pdfUrl: URL(string: "https://arxiv.org/pdf/\(id)")!,
            firstSeenAt: date(0),
            categories: ["cs.AI"],
            relevance: relevance,
            novelty: novelty,
            topicAssignments: [TopicAssignment(topicId: topicID, subtopicIds: [subtopicID])],
            selectionReason: "Fixture",
            tldr: summary,
            bullets: ["One", "Two", "Three"],
            summaryStatus: .generated,
            heroFigure: nil,
            figureStatus: .notImplemented
        )
        let result = PersonalPaperState(canonicalArxivID: id)
        result.seen = true
        result.saved = saved
        result.savedAt = date(1)
        result.lastSavedAt = date(2)
        result.readingStatus = status
        result.snapshot = SavedPaperSnapshot(paper: paper, capturedAt: date(2))
        return result
    }

    private func topicIndex() -> TopicsIndex {
        TopicsIndex(
            schemaVersion: 1,
            taxonomyVersion: 1,
            totalPaperCount: 1,
            topics: [
                PublicTopic(
                    id: "world-models",
                    name: "World Models",
                    paperCount: 1,
                    feedUrl: "topics/world-models.json",
                    subtopics: [
                        PublicSubtopic(
                            id: "video-world-models",
                            name: "Video World Models",
                            paperCount: 1,
                            feedUrl: "topics/video-world-models.json"
                        )
                    ]
                )
            ]
        )
    }

    private func date(_ hour: Int) -> Date {
        Date(timeIntervalSince1970: TimeInterval(hour * 3_600))
    }
}
