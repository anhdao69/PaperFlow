import SwiftData
import XCTest
@testable import PaperFlow

@MainActor
final class SwiftDataPersistenceTests: XCTestCase {
    func testInMemoryCrossContextUniquenessAndObservation() throws {
        let container = try makeContainer(inMemory: true)
        let firstStore = SwiftDataPersonalPaperStore(modelContainer: container)
        let service = PersonalActionService(store: firstStore, clock: { self.date(1) })
        try service.save(paper("2608.20001v1"))

        let secondStore = SwiftDataPersonalPaperStore(modelContainer: container)
        let observed = try XCTUnwrap(secondStore.state(for: "2608.20001v2"))
        XCTAssertTrue(observed.saved)
        XCTAssertEqual(observed.snapshot?.title, "Persistent paper")
        XCTAssertEqual(try secondStore.allStates().count, 1)
    }

    func testDiskBackedRestartRetainsPersonalStateAndSnapshot() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("PaperFlow-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let storeURL = directory.appendingPathComponent("personal.store")

        do {
            let container = try makeContainer(inMemory: false, url: storeURL)
            let store = SwiftDataPersonalPaperStore(modelContainer: container)
            let service = PersonalActionService(
                store: store,
                clock: { self.date(1) }
            )
            let item = paper("2608.20002")
            try service.save(item)
            try service.updateNote(arxivID: item.arxivId, note: "Offline note")
            try service.updateRating(arxivID: item.arxivId, rating: 4)
            try service.transition(arxivID: item.arxivId, to: .done)
        }

        do {
            let container = try makeContainer(inMemory: false, url: storeURL)
            let store = SwiftDataPersonalPaperStore(modelContainer: container)
            let restored = try XCTUnwrap(store.state(for: "2608.20002v9"))
            XCTAssertTrue(restored.saved)
            XCTAssertEqual(restored.readingStatus, .done)
            XCTAssertEqual(restored.note, "Offline note")
            XCTAssertEqual(restored.rating, 4)
            XCTAssertEqual(restored.snapshot?.displaySummary, "Persistent summary")
        }
    }

    func testSnapshotRefreshDoesNotChangePersonalFields() throws {
        let container = try makeContainer(inMemory: true)
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        var times = [date(1), date(2)].makeIterator()
        let service = PersonalActionService(store: store) { times.next() ?? self.date(99) }
        let original = paper("2608.20003")
        let state = try service.save(original)
        try service.updateNote(arxivID: original.arxivId, note: "Personal")
        let savedAt = state.savedAt

        let refreshed = PublicPaper(
            arxivId: original.arxivId,
            title: "Refreshed title",
            authors: original.authors,
            abstract: original.abstract,
            arxivUrl: original.arxivUrl,
            pdfUrl: original.pdfUrl,
            firstSeenAt: original.firstSeenAt,
            categories: original.categories,
            relevance: original.relevance,
            novelty: original.novelty,
            topicAssignments: original.topicAssignments,
            selectionReason: original.selectionReason,
            tldr: original.tldr,
            bullets: original.bullets,
            summaryStatus: original.summaryStatus,
            heroFigure: original.heroFigure,
            figureStatus: original.figureStatus
        )
        try service.refreshSnapshot(with: refreshed)

        XCTAssertEqual(state.snapshot?.title, "Refreshed title")
        XCTAssertEqual(state.note, "Personal")
        XCTAssertEqual(state.savedAt, savedAt)
    }

    private func makeContainer(inMemory: Bool, url: URL? = nil) throws -> ModelContainer {
        let schema = Schema([PersonalPaperState.self, SavedPaperSnapshot.self])
        let configuration: ModelConfiguration
        if let url {
            configuration = ModelConfiguration(schema: schema, url: url)
        } else {
            configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: inMemory)
        }
        return try ModelContainer(for: schema, configurations: [configuration])
    }

    private func date(_ hour: Int) -> Date {
        Date(timeIntervalSince1970: TimeInterval(hour * 3_600))
    }

    private func paper(_ id: String) -> PublicPaper {
        PublicPaper(
            arxivId: id,
            title: "Persistent paper",
            authors: ["Grace Scientist"],
            abstract: "Persistent abstract",
            arxivUrl: URL(string: "https://arxiv.org/abs/2608.20000")!,
            pdfUrl: URL(string: "https://arxiv.org/pdf/2608.20000")!,
            firstSeenAt: date(0),
            categories: ["cs.LG"],
            relevance: 8,
            novelty: 7,
            topicAssignments: [TopicAssignment(topicId: "agents", subtopicIds: [])],
            selectionReason: "Fixture",
            tldr: "Persistent summary",
            bullets: ["One", "Two", "Three"],
            summaryStatus: .generated,
            heroFigure: nil,
            figureStatus: .notImplemented
        )
    }
}
