import Foundation

enum TopicsViewModel {
    static func uniqueTotal(_ index: TopicsIndex) -> Int {
        index.totalPaperCount
    }

    static func topic(for id: String, in index: TopicsIndex) -> PublicTopic? {
        index.topics.first { $0.id == id }
    }
}
