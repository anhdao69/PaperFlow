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
    private(set) var refreshMessage: String?
    private(set) var isRefreshing = false
    private let source: any PaperFlowDataSource
    private let clock: @MainActor () -> Date

    var dailyFeed: DailyFeed? { dayFeeds.values.sorted { $0.date > $1.date }.first }
    var currentDate: Date { clock() }

    init(
        client: any PublicFeedClientProtocol = BundledFixtureFeedClient(),
        clock: @escaping @MainActor () -> Date = Date.init,
        reportsCachedData: Bool = false
    ) {
        source = DirectPublicFeedDataSource(
            client: client,
            clock: { Date() },
            reportedSource: reportsCachedData ? .cache : .network,
            refreshErrorDescription: reportsCachedData
                ? "Couldn’t refresh PaperFlow. Showing your latest downloaded data."
                : nil
        )
        self.clock = clock
    }

    init(source: any PaperFlowDataSource, clock: @escaping @MainActor () -> Date = Date.init) {
        self.source = source
        self.clock = clock
    }

    static func production(bundle: Bundle = .main) -> AppModel {
        guard let value = bundle.object(forInfoDictionaryKey: "PaperFlowBaseURL") as? String,
              let url = URL(string: value),
              let client = try? PublicFeedClient(publicationRoot: url),
              let root = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
              ).first else {
            return AppModel(source: UnavailablePublicFeedDataSource())
        }
        let cache = FilePublicFeedCache(
            directory: root.appendingPathComponent("PaperFlow/PublicFeed", isDirectory: true)
        )
        return AppModel(source: PaperFlowRepository(client: client, cache: cache))
    }

    func loadFixtureShellIfNeeded() async {
        guard loadState == .idle else { return }
        await loadInitialContent()
    }

    func refresh() async {
        await loadInitialContent(preservingLoadedContent: true)
    }

    private func loadInitialContent(preservingLoadedContent: Bool = false) async {
        isRefreshing = true
        defer { isRefreshing = false }
        if !preservingLoadedContent { loadState = .loading }
        refreshMessage = nil
        isShowingCachedData = false
        do {
            async let indexResult = source.feedIndex()
            async let topicsResult = source.topicsIndex()
            let loadedIndex = try await indexResult
            let loadedTopics = try await topicsResult
            recordMetadata(loadedIndex)
            recordMetadata(loadedTopics)
            let dayResult: PublicFeedResult<DailyFeed>?
            if let firstDay = loadedIndex.value.days.first {
                dayResult = try await source.dailyFeed(relativePath: firstDay.feedUrl)
            } else {
                dayResult = nil
            }
            feedIndex = loadedIndex.value
            topicsIndex = loadedTopics.value
            if let dayResult {
                recordMetadata(dayResult)
                dayFeeds[dayResult.value.date] = dayResult.value
            }
            loadState = .loaded
        } catch {
            if preservingLoadedContent, feedIndex != nil, topicsIndex != nil {
                loadState = .loaded
                isShowingCachedData = true
                refreshMessage = "Couldn’t refresh PaperFlow. Showing your latest downloaded data."
            } else {
                loadState = .failed("PaperFlow data is unavailable. Check your connection and try again.")
            }
        }
    }

    func loadDay(_ day: FeedDay) async {
        guard dayFeeds[day.date] == nil else { return }
        do {
            let result = try await source.dailyFeed(relativePath: day.feedUrl)
            let feed = result.value
            guard feed.date == day.date, feed.paperCount == day.paperCount else {
                throw PublicContractError.invalidCount
            }
            recordMetadata(result)
            dayFeeds[day.date] = feed
            dayErrors[day.date] = nil
        } catch {
            dayErrors[day.date] = "This day is unavailable. Try again when a connection is available."
        }
    }

    func loadTopicFeed(relativePath: String) async {
        guard topicFeeds[relativePath] == nil else { return }
        do {
            let result = try await source.topicFeed(relativePath: relativePath)
            recordMetadata(result)
            topicFeeds[relativePath] = result.value
            topicErrors[relativePath] = nil
        } catch {
            topicErrors[relativePath] = "This topic history is unavailable. Try again when connected."
        }
    }

    private func recordMetadata<Value>(_ result: PublicFeedResult<Value>) {
        if lastUpdatedAt == nil || result.lastSuccessfulRefresh > lastUpdatedAt! {
            lastUpdatedAt = result.lastSuccessfulRefresh
        }
        if result.source == .cache { isShowingCachedData = true }
        if let message = result.refreshErrorDescription { refreshMessage = message }
    }
}

private actor UnavailablePublicFeedDataSource: PaperFlowDataSource {
    func feedIndex() async throws -> PublicFeedResult<FeedIndex> { throw URLError(.notConnectedToInternet) }
    func topicsIndex() async throws -> PublicFeedResult<TopicsIndex> { throw URLError(.notConnectedToInternet) }
    func dailyFeed(relativePath: String) async throws -> PublicFeedResult<DailyFeed> {
        throw URLError(.notConnectedToInternet)
    }
    func topicFeed(relativePath: String) async throws -> PublicFeedResult<TopicFeed> {
        throw URLError(.notConnectedToInternet)
    }
}
