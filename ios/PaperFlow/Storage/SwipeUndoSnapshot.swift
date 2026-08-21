import Foundation

struct SavedPaperSnapshotValue: Equatable, Sendable {
    let canonicalArxivID: String
    let title: String
    let authors: [String]
    let abstract: String
    let displaySummary: String
    let arxivURL: URL
    let pdfURL: URL
    let topicIDs: [String]
    let subtopicIDs: [String]
    let relevance: Int
    let novelty: Int
    let heroFigure: String?
    let figureStatusRawValue: String?
    let topicAssignmentsData: Data?
    let capturedAt: Date

    init(_ snapshot: SavedPaperSnapshot) {
        canonicalArxivID = snapshot.canonicalArxivID
        title = snapshot.title
        authors = snapshot.authors
        abstract = snapshot.abstract
        displaySummary = snapshot.displaySummary
        arxivURL = snapshot.arxivURL
        pdfURL = snapshot.pdfURL
        topicIDs = snapshot.topicIDs
        subtopicIDs = snapshot.subtopicIDs
        relevance = snapshot.relevance
        novelty = snapshot.novelty
        heroFigure = snapshot.heroFigure
        figureStatusRawValue = snapshot.figureStatusRawValue
        topicAssignmentsData = snapshot.topicAssignmentsData
        capturedAt = snapshot.capturedAt
    }
}

struct PersonalPaperStateValue: Equatable, Sendable {
    let canonicalArxivID: String
    let seen: Bool
    let lastSeenAt: Date?
    let saved: Bool
    let savedAt: Date?
    let lastSavedAt: Date?
    let unsavedAt: Date?
    let readingStatus: ReadingStatus?
    let statusChangedAt: Date?
    let startedReadingAt: Date?
    let completedAt: Date?
    let lastOpenedAt: Date?
    let note: String
    let rating: Int?
    let snapshot: SavedPaperSnapshotValue?

    init(_ state: PersonalPaperState) {
        canonicalArxivID = state.canonicalArxivID
        seen = state.seen
        lastSeenAt = state.lastSeenAt
        saved = state.saved
        savedAt = state.savedAt
        lastSavedAt = state.lastSavedAt
        unsavedAt = state.unsavedAt
        readingStatus = state.readingStatus
        statusChangedAt = state.statusChangedAt
        startedReadingAt = state.startedReadingAt
        completedAt = state.completedAt
        lastOpenedAt = state.lastOpenedAt
        note = state.note
        rating = state.rating
        snapshot = state.snapshot.map(SavedPaperSnapshotValue.init)
    }
}

struct SwipeUndoSnapshot: Equatable, Sendable {
    let canonicalArxivID: String
    let priorState: PersonalPaperStateValue?
}
