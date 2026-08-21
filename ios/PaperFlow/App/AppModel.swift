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
    private(set) var dailyFeed: DailyFeed?
    private let client: any PublicFeedClientProtocol

    init(client: any PublicFeedClientProtocol = BundledFixtureFeedClient()) {
        self.client = client
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
                day = try await client.fetchDailyFeed(
                    relativePath: firstDay.feedUrl
                ).validated()
            } else {
                day = nil
            }
            feedIndex = loadedIndex
            topicsIndex = loadedTopics
            dailyFeed = day
            loadState = .loaded
        } catch {
            loadState = .failed("PaperFlow fixture data could not be loaded.")
        }
    }
}
