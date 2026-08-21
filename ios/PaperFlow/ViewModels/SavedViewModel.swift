import Foundation

enum SavedSort: String, CaseIterable, Identifiable {
    case recentlySaved = "Recently Saved"
    case oldestSaved = "Oldest Saved"
    case relevance = "Relevance"
    case novelty = "Novelty"
    case title = "Title"
    case lastOpened = "Last Opened"
    case recentlyCompleted = "Recently Completed"
    case oldestCompleted = "Oldest Completed"

    var id: String { rawValue }

    static func options(for status: ReadingStatus) -> [SavedSort] {
        switch status {
        case .queue: [.recentlySaved, .oldestSaved, .relevance, .novelty, .title]
        case .reading: [.lastOpened, .recentlySaved, .title]
        case .done: [.recentlyCompleted, .oldestCompleted, .title]
        }
    }

    static func defaultSort(for status: ReadingStatus) -> SavedSort {
        switch status {
        case .queue: .recentlySaved
        case .reading: .lastOpened
        case .done: .recentlyCompleted
        }
    }
}

struct SavedCounts: Equatable {
    let queue: Int
    let reading: Int
    let done: Int

    var total: Int { queue + reading + done }

    subscript(status: ReadingStatus) -> Int {
        switch status {
        case .queue: queue
        case .reading: reading
        case .done: done
        }
    }
}

enum SavedViewModel {
    static func counts(_ states: [PersonalPaperState]) -> SavedCounts {
        let records = uniqueSavedStates(states)
        return SavedCounts(
            queue: records.filter { ($0.readingStatus ?? .queue) == .queue }.count,
            reading: records.filter { $0.readingStatus == .reading }.count,
            done: records.filter { $0.readingStatus == .done }.count
        )
    }

    static func records(
        _ states: [PersonalPaperState],
        status: ReadingStatus,
        query: String = "",
        sort: SavedSort? = nil,
        topics: TopicsIndex? = nil
    ) -> [PersonalPaperState] {
        let selectedSort = sort ?? SavedSort.defaultSort(for: status)
        return uniqueSavedStates(states)
            .filter { ($0.readingStatus ?? .queue) == status }
            .filter { SavedSearch.matches(query: query, state: $0, topics: topics) }
            .sorted { ordered($0, before: $1, by: selectedSort) }
    }

    private static func uniqueSavedStates(_ states: [PersonalPaperState]) -> [PersonalPaperState] {
        var seen: Set<String> = []
        return states.filter { state in
            guard state.saved, state.snapshot != nil else { return false }
            return seen.insert(state.canonicalArxivID).inserted
        }
    }

    private static func ordered(
        _ lhs: PersonalPaperState,
        before rhs: PersonalPaperState,
        by sort: SavedSort
    ) -> Bool {
        let comparison: ComparisonResult
        switch sort {
        case .recentlySaved:
            comparison = compareDates(lhs.lastSavedAt, rhs.lastSavedAt, descending: true)
        case .oldestSaved:
            comparison = compareDates(lhs.savedAt, rhs.savedAt, descending: false)
        case .relevance:
            comparison = compareInts(lhs.snapshot?.relevance, rhs.snapshot?.relevance, descending: true)
        case .novelty:
            comparison = compareInts(lhs.snapshot?.novelty, rhs.snapshot?.novelty, descending: true)
        case .title:
            comparison = .orderedSame
        case .lastOpened:
            comparison = compareDateChains(
                [lhs.lastOpenedAt, lhs.statusChangedAt, lhs.lastSavedAt],
                [rhs.lastOpenedAt, rhs.statusChangedAt, rhs.lastSavedAt]
            )
        case .recentlyCompleted:
            comparison = compareDates(lhs.completedAt, rhs.completedAt, descending: true)
        case .oldestCompleted:
            comparison = compareDates(lhs.completedAt, rhs.completedAt, descending: false)
        }
        if comparison != .orderedSame { return comparison == .orderedAscending }

        let lhsTitle = lhs.snapshot?.title ?? ""
        let rhsTitle = rhs.snapshot?.title ?? ""
        let titleComparison = lhsTitle.localizedCaseInsensitiveCompare(rhsTitle)
        if titleComparison != .orderedSame { return titleComparison == .orderedAscending }
        return lhs.canonicalArxivID < rhs.canonicalArxivID
    }

    private static func compareDateChains(_ lhs: [Date?], _ rhs: [Date?]) -> ComparisonResult {
        for (left, right) in zip(lhs, rhs) {
            let result = compareDates(left, right, descending: true)
            if result != .orderedSame { return result }
        }
        return .orderedSame
    }

    private static func compareDates(_ lhs: Date?, _ rhs: Date?, descending: Bool) -> ComparisonResult {
        switch (lhs, rhs) {
        case let (left?, right?) where left != right:
            let leftFirst = descending ? left > right : left < right
            return leftFirst ? .orderedAscending : .orderedDescending
        case (_?, nil): return .orderedAscending
        case (nil, _?): return .orderedDescending
        default: return .orderedSame
        }
    }

    private static func compareInts(_ lhs: Int?, _ rhs: Int?, descending: Bool) -> ComparisonResult {
        switch (lhs, rhs) {
        case let (left?, right?) where left != right:
            let leftFirst = descending ? left > right : left < right
            return leftFirst ? .orderedAscending : .orderedDescending
        case (_?, nil): return .orderedAscending
        case (nil, _?): return .orderedDescending
        default: return .orderedSame
        }
    }
}
