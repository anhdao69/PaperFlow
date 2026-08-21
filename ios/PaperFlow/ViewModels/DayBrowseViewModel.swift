import Foundation
import Observation

enum DayBrowseSort: String, CaseIterable, Identifiable {
    case relevance = "Relevance"
    case newest = "Newest"
    case novelty = "Novelty"
    case title = "Title"

    var id: Self { self }
}

enum DayBrowseStatus: String, CaseIterable, Identifiable {
    case all = "All"
    case unread = "Unread"
    case reviewed = "Reviewed"
    case saved = "Saved"

    var id: Self { self }
}

@Observable
final class DayBrowseViewModel {
    let feed: DailyFeed
    let topics: TopicsIndex?
    var sort: DayBrowseSort = .relevance
    var status: DayBrowseStatus = .all
    var selectedTopicIDs: Set<String> = []

    init(feed: DailyFeed, topics: TopicsIndex?) {
        self.feed = feed
        self.topics = topics
    }

    var availableTopics: [PublicTopic] {
        let assigned = Set(feed.papers.flatMap { $0.topicAssignments.map(\.topicId) })
        return (topics?.topics ?? []).filter { assigned.contains($0.id) }
    }

    func visiblePapers(personalStates: [PersonalPaperState]) -> [PublicPaper] {
        let stateByID = Dictionary(
            uniqueKeysWithValues: personalStates.map { ($0.canonicalArxivID, $0) }
        )
        return feed.papers
            .filter { paper in
                selectedTopicIDs.isEmpty
                    || paper.topicAssignments.contains { selectedTopicIDs.contains($0.topicId) }
            }
            .filter { paper in
                let state = stateByID[PublicPaper.normalizeArxivID(paper.arxivId)]
                switch status {
                case .all: return true
                case .unread: return state?.seen != true
                case .reviewed: return state?.seen == true
                case .saved: return state?.saved == true
                }
            }
            .sorted { lhs, rhs in
                compare(lhs, rhs)
            }
    }

    func resetFilters() {
        selectedTopicIDs = []
        status = .all
        sort = .relevance
    }

    private func compare(_ lhs: PublicPaper, _ rhs: PublicPaper) -> Bool {
        switch sort {
        case .relevance where lhs.relevance != rhs.relevance:
            return lhs.relevance > rhs.relevance
        case .newest where lhs.firstSeenAt != rhs.firstSeenAt:
            return lhs.firstSeenAt > rhs.firstSeenAt
        case .novelty where lhs.novelty != rhs.novelty:
            return lhs.novelty > rhs.novelty
        default:
            let titleOrder = lhs.title.localizedCaseInsensitiveCompare(rhs.title)
            if titleOrder != .orderedSame { return titleOrder == .orderedAscending }
            return lhs.arxivId < rhs.arxivId
        }
    }
}
