import Foundation

enum ReadingStatus: String, Codable, CaseIterable, Sendable {
    case queue
    case reading
    case done
}

enum PersonalStateError: Error, Equatable {
    case missingSavedState
    case invalidRating
    case missingUndo
}
