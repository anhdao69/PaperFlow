import Foundation

enum SavedSearch {
    static func matches(
        query: String,
        state: PersonalPaperState,
        topics: TopicsIndex?
    ) -> Bool {
        let needle = normalized(query.trimmingCharacters(in: .whitespacesAndNewlines))
        guard !needle.isEmpty else { return true }
        guard let snapshot = state.snapshot else { return false }

        let labels = topicLabels(snapshot: snapshot, topics: topics)
        let searchable = [
            snapshot.title,
            snapshot.authors.joined(separator: " "),
            snapshot.displaySummary,
            labels.joined(separator: " "),
            state.note,
        ]
        return searchable.contains { normalized($0).contains(needle) }
    }

    static func topicLabels(snapshot: SavedPaperSnapshot, topics: TopicsIndex?) -> [String] {
        guard let topics else { return snapshot.topicIDs + snapshot.subtopicIDs }
        var labels: [String] = []
        for topic in topics.topics where snapshot.topicIDs.contains(topic.id) {
            labels.append(topic.name)
            labels.append(contentsOf: topic.subtopics.filter {
                snapshot.subtopicIDs.contains($0.id)
            }.map(\.name))
        }
        return labels
    }

    private static func normalized(_ value: String) -> String {
        value.folding(
            options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive],
            locale: .current
        )
    }
}
