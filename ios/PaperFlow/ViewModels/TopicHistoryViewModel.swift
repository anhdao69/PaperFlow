import Foundation
import Observation

@Observable
final class TopicHistoryViewModel {
    let feed: TopicFeed
    let topic: PublicTopic
    let subtopic: PublicSubtopic?
    var sort: DayBrowseSort = .relevance
    var status: DayBrowseStatus = .all
    var selectedSubtopicIDs: Set<String> = []

    init(feed: TopicFeed, topic: PublicTopic, subtopic: PublicSubtopic? = nil) {
        self.feed = feed
        self.topic = topic
        self.subtopic = subtopic
    }

    var papers: [PublicPaper] { feed.days.flatMap(\.papers) }
    var dayCounts: [(date: Date, count: Int)] { feed.days.map { ($0.date, $0.paperCount) } }

    func visiblePapers(personalStates: [PersonalPaperState]) -> [PublicPaper] {
        let stateByID = Dictionary(
            uniqueKeysWithValues: personalStates.map { ($0.canonicalArxivID, $0) }
        )
        return papers
            .filter { paper in
                guard subtopic == nil, !selectedSubtopicIDs.isEmpty else { return true }
                return paper.topicAssignments.contains { assignment in
                    assignment.topicId == topic.id
                        && !selectedSubtopicIDs.isDisjoint(with: assignment.subtopicIds)
                }
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
            .sorted(by: compare)
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
