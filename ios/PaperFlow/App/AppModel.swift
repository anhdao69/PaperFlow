import Foundation
import Observation

@MainActor
@Observable
final class AppModel {
    enum LoadState: Equatable {
        case idle
        case loading
        case loaded
        case failed(String)
    }

    private(set) var loadState: LoadState = .idle
    private(set) var feedIndex: FeedIndex?
    private(set) var topicsIndex: TopicsIndex?
    private(set) var dayFeeds: [Date: DailyFeed] = [:]
    private(set) var dayErrors: [Date: String] = [:]
    private(set) var topicFeeds: [String: TopicFeed] = [:]
    private(set) var topicErrors: [String: String] = [:]
    private(set) var lastUpdatedAt: Date?
    private(set) var isShowingCachedData = false
    private let client: any PublicFeedClientProtocol
    private let clock: @MainActor () -> Date

    var dailyFeed: DailyFeed? { dayFeeds.values.sorted { $0.date > $1.date }.first }
    var currentDate: Date { clock() }

    init(
        client: any PublicFeedClientProtocol = BundledFixtureFeedClient(),
        clock: @escaping @MainActor () -> Date = Date.init
    ) {
        self.client = client
        self.clock = clock
    }

    func loadFixtureShellIfNeeded() async {
        guard loadState == .idle else { return }
        loadState = .loading
        do {
            async let index = client.fetchFeedIndex()
            async let topics = client.fetchTopicsIndex()
            let loadedIndex = try await index.validated()
            let loadedTopics = try await topics.validated()
            let day: DailyFeed?
            if let firstDay = loadedIndex.days.first {
                day = try await client.fetchDailyFeed(relativePath: firstDay.feedUrl).validated()
            } else {
                day = nil
            }
            feedIndex = loadedIndex
            topicsIndex = loadedTopics
            if let day { dayFeeds[day.date] = day }
            lastUpdatedAt = clock()
            loadState = .loaded
        } catch {
            loadState = .failed("PaperFlow fixture data could not be loaded.")
        }
    }

    func loadDay(_ day: FeedDay) async {
        guard dayFeeds[day.date] == nil else { return }
        do {
            let feed = try await client.fetchDailyFeed(relativePath: day.feedUrl).validated()
            guard feed.date == day.date, feed.paperCount == day.paperCount else {
                throw PublicContractError.invalidCount
            }
            dayFeeds[day.date] = feed
            dayErrors[day.date] = nil
        } catch {
            dayErrors[day.date] = "This day is unavailable. Try again when a connection is available."
        }
    }

    func loadTopicFeed(relativePath: String) async {
        guard topicFeeds[relativePath] == nil else { return }
        do {
            topicFeeds[relativePath] = try await client.fetchTopicFeed(
                relativePath: relativePath
            ).validated()
            topicErrors[relativePath] = nil
        } catch {
            topicErrors[relativePath] = "This topic history is unavailable. Try again when connected."
        }
    }
}
