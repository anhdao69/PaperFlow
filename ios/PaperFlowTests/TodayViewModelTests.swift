import SwiftData
import XCTest
@testable import PaperFlow

@MainActor
final class TodayViewModelTests: XCTestCase {
    func testPublicationDateUsesFeedTimezoneAcrossDeviceTravelBoundary() throws {
        let instant = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-08-21T02:00:00Z"))

        let newYorkDay = try TodayViewModel.publicationDate(
            now: instant,
            timezoneID: "America/New_York"
        )
        let tokyoDay = try TodayViewModel.publicationDate(
            now: instant,
            timezoneID: "Asia/Tokyo"
        )

        XCTAssertEqual(PFDateText.identifier(newYorkDay), "2026-08-20")
        XCTAssertEqual(PFDateText.identifier(tokyoDay), "2026-08-21")
        XCTAssertThrowsError(
            try TodayViewModel.publicationDate(now: instant, timezoneID: "Not/A_Timezone")
        )
    }

    func testPresentZeroDayIsTodayButAbsentDayIsLatestAvailable() throws {
        let now = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-08-20T16:00:00Z"))
        let today = day("2026-08-20", count: 0)
        let yesterday = day("2026-08-19", count: 35)

        XCTAssertEqual(
            try TodayViewModel.selection(for: index([today, yesterday]), now: now),
            .current(today)
        )
        XCTAssertEqual(
            try TodayViewModel.selection(for: index([yesterday]), now: now),
            .unavailable(latest: yesterday)
        )
        XCTAssertEqual(
            try TodayViewModel.selection(for: index([]), now: now),
            .unavailable(latest: nil)
        )
    }

    func testProgressUsesExactServerTotalAndOnlyGlobalSeenState() {
        let first = paper("2608.00001", title: "First", relevance: 8, novelty: 7, hour: 1)
        let second = paper("2608.00002", title: "Second", relevance: 7, novelty: 8, hour: 2)
        let seen = PersonalPaperState(canonicalArxivID: first.arxivId)
        seen.seen = true
        let unrelated = PersonalPaperState(canonicalArxivID: "2608.99999")
        unrelated.seen = true
        let feed = DailyFeed(schemaVersion: 1, date: fixtureDay, paperCount: 2, papers: [first, second])

        let progress = TodayViewModel.progress(for: feed, personalStates: [seen, unrelated])

        XCTAssertEqual(progress, CollectionProgress(reviewed: 1, total: 2))
        XCTAssertEqual(progress.remaining, 1)
        XCTAssertEqual(progress.percentage, 50)
        XCTAssertEqual(CollectionProgress(reviewed: 0, total: 0).percentage, 0)
    }

    func testAllHistoryBeyondNewestEightyRemainsReachable() throws {
        let now = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-08-20T16:00:00Z"))
        let days = (0 ..< 81).map { offset in
            FeedDay(
                date: fixtureDay.addingTimeInterval(TimeInterval(-86_400 * offset)),
                paperCount: 1,
                feedUrl: "data/daily_feeds/day-\(offset).json"
            )
        }

        let previous = try TodayViewModel.previousDays(for: index(days), now: now)

        XCTAssertEqual(previous.count, 80)
        XCTAssertEqual(previous.last?.feedUrl, "data/daily_feeds/day-80.json")
    }

    func testBrowseSortsFiltersAndRenderingNeverMutatePersonalState() {
        let alpha = paper("2608.00003", title: "alpha", relevance: 8, novelty: 7, hour: 1)
        let beta = paper("2608.00002", title: "Beta", relevance: 8, novelty: 9, hour: 3)
        let gamma = paper("2608.00001", title: "Gamma", relevance: 6, novelty: 9, hour: 2)
        let feed = DailyFeed(
            schemaVersion: 1,
            date: fixtureDay,
            paperCount: 3,
            papers: [gamma, beta, alpha]
        )
        let state = PersonalPaperState(canonicalArxivID: beta.arxivId)
        state.seen = true
        state.saved = true
        let before = PersonalPaperStateValue(state)
        let model = DayBrowseViewModel(feed: feed, topics: topicsIndex())

        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.title), ["alpha", "Beta", "Gamma"])
        model.sort = .novelty
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.title), ["Beta", "Gamma", "alpha"])
        model.sort = .newest
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.title), ["Beta", "Gamma", "alpha"])
        model.sort = .title
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.title), ["alpha", "Beta", "Gamma"])

        model.status = .unread
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.arxivId), [alpha.arxivId, gamma.arxivId])
        model.status = .saved
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.arxivId), [beta.arxivId])
        model.status = .all
        model.selectedTopicIDs = ["topic-b"]
        XCTAssertEqual(model.visiblePapers(personalStates: [state]).map(\.arxivId), [gamma.arxivId])
        XCTAssertEqual(PersonalPaperStateValue(state), before)
    }

    func testSaveImmediatelyUpdatesProgressAndBrowseAcrossOneSwiftDataState() throws {
        let container = try ModelContainer(
            for: PersonalPaperState.self,
            SavedPaperSnapshot.self,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let store = SwiftDataPersonalPaperStore(modelContainer: container)
        let service = PersonalActionService(store: store, clock: { Date(timeIntervalSince1970: 100) })
        let item = paper("2608.00004", title: "Shared", relevance: 9, novelty: 9, hour: 4)
        let feed = DailyFeed(schemaVersion: 1, date: fixtureDay, paperCount: 1, papers: [item])
        let browse = DayBrowseViewModel(feed: feed, topics: topicsIndex())

        XCTAssertEqual(TodayViewModel.progress(for: feed, personalStates: try store.allStates()).reviewed, 0)
        try service.save(item)
        let states = try store.allStates()

        XCTAssertEqual(TodayViewModel.progress(for: feed, personalStates: states).reviewed, 1)
        browse.status = .saved
        XCTAssertEqual(browse.visiblePapers(personalStates: states).map(\.arxivId), [item.arxivId])
        XCTAssertEqual(states.count, 1)
    }

    private func index(_ days: [FeedDay]) -> FeedIndex {
        FeedIndex(
            schemaVersion: 1,
            generatedAt: fixtureDay,
            timezone: "America/New_York",
            totalPaperCount: days.reduce(0) { $0 + $1.paperCount },
            dayCount: days.count,
            days: days
        )
    }

    private func day(_ value: String, count: Int) -> FeedDay {
        FeedDay(
            date: try! PublicFeedDecoder.decode(DateBox.self, from: Data(#"{"date":"\#(value)"}"#.utf8)).date,
            paperCount: count,
            feedUrl: "data/daily_feeds/\(value).json"
        )
    }
}

private struct DateBox: Decodable { let date: Date }

private let fixtureDay = Date(timeIntervalSince1970: 1_787_184_000)

private func paper(
    _ id: String,
    title: String,
    relevance: Int,
    novelty: Int,
    hour: Int
) -> PublicPaper {
    let topicID = title == "Gamma" ? "topic-b" : "topic-a"
    return PublicPaper(
        arxivId: id,
        title: title,
        authors: ["Test Author"],
        abstract: String(repeating: "A complete abstract. ", count: 30),
        arxivUrl: URL(string: "https://arxiv.org/abs/\(id)")!,
        pdfUrl: URL(string: "https://arxiv.org/pdf/\(id)")!,
        firstSeenAt: fixtureDay.addingTimeInterval(TimeInterval(hour * 3_600)),
        categories: ["cs.AI"],
        relevance: relevance,
        novelty: novelty,
        topicAssignments: [TopicAssignment(topicId: topicID, subtopicIds: [])],
        selectionReason: "Matches the configured research interests.",
        tldr: nil,
        bullets: [],
        summaryStatus: .failed,
        heroFigure: nil,
        figureStatus: .notImplemented
    )
}

private func topicsIndex() -> TopicsIndex {
    TopicsIndex(
        schemaVersion: 1,
        taxonomyVersion: 1,
        totalPaperCount: 3,
        topics: [
            PublicTopic(id: "topic-a", name: "Topic A", paperCount: 2, feedUrl: "data/a.json", subtopics: []),
            PublicTopic(id: "topic-b", name: "Topic B", paperCount: 1, feedUrl: "data/b.json", subtopics: [])
        ]
    )
}
