import Foundation

enum ReadingStatus: String, Codable, CaseIterable, Sendable {
    case queue
    case reading
    case done
}

extension ReadingStatus {
    var displayName: String {
        switch self {
        case .queue: "Queue"
        case .reading: "Reading"
        case .done: "Done"
        }
    }

    var systemImage: String {
        switch self {
        case .queue: "bookmark"
        case .reading: "book"
        case .done: "checkmark.circle"
        }
    }
}

enum PersonalStateError: Error, Equatable {
    case missingSavedState
    case invalidRating
    case missingUndo
}
