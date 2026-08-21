import Foundation
import SwiftData

@Model
final class PersonalPaperState {
    @Attribute(.unique) var canonicalArxivID: String
    var seen: Bool
    var lastSeenAt: Date?
    var saved: Bool
    var savedAt: Date?
    var lastSavedAt: Date?
    var unsavedAt: Date?
    var readingStatusRawValue: String?
    var statusChangedAt: Date?
    var startedReadingAt: Date?
    var completedAt: Date?
    var lastOpenedAt: Date?
    var note: String
    var rating: Int?
    @Relationship(deleteRule: .cascade) var snapshot: SavedPaperSnapshot?

    var readingStatus: ReadingStatus? {
        get { readingStatusRawValue.flatMap(ReadingStatus.init(rawValue:)) }
        set { readingStatusRawValue = newValue?.rawValue }
    }

    init(canonicalArxivID: String) {
        self.canonicalArxivID = PublicPaper.normalizeArxivID(canonicalArxivID)
        seen = false
        saved = false
        note = ""
    }
}
