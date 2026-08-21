import Foundation
import SwiftData

@Model
final class SavedPaperSnapshot {
    @Attribute(.unique) var canonicalArxivID: String
    var title: String
    var authors: [String]
    var abstract: String
    var displaySummary: String
    var arxivURL: URL
    var pdfURL: URL
    var topicIDs: [String]
    var subtopicIDs: [String]
    var relevance: Int
    var novelty: Int
    var capturedAt: Date

    init(paper: PublicPaper, capturedAt: Date) {
        canonicalArxivID = PublicPaper.normalizeArxivID(paper.arxivId)
        title = paper.title
        authors = paper.authors
        abstract = paper.abstract
        displaySummary = paper.displaySummary
        arxivURL = paper.arxivUrl
        pdfURL = paper.pdfUrl
        topicIDs = paper.topicAssignments.map(\.topicId)
        subtopicIDs = paper.topicAssignments.flatMap(\.subtopicIds)
        relevance = paper.relevance
        novelty = paper.novelty
        self.capturedAt = capturedAt
    }

    init(value: SavedPaperSnapshotValue) {
        canonicalArxivID = value.canonicalArxivID
        title = value.title
        authors = value.authors
        abstract = value.abstract
        displaySummary = value.displaySummary
        arxivURL = value.arxivURL
        pdfURL = value.pdfURL
        topicIDs = value.topicIDs
        subtopicIDs = value.subtopicIDs
        relevance = value.relevance
        novelty = value.novelty
        capturedAt = value.capturedAt
    }

    func refresh(from paper: PublicPaper, capturedAt: Date) {
        title = paper.title
        authors = paper.authors
        abstract = paper.abstract
        displaySummary = paper.displaySummary
        arxivURL = paper.arxivUrl
        pdfURL = paper.pdfUrl
        topicIDs = paper.topicAssignments.map(\.topicId)
        subtopicIDs = paper.topicAssignments.flatMap(\.subtopicIds)
        relevance = paper.relevance
        novelty = paper.novelty
        self.capturedAt = capturedAt
    }

    func restore(_ value: SavedPaperSnapshotValue) {
        title = value.title
        authors = value.authors
        abstract = value.abstract
        displaySummary = value.displaySummary
        arxivURL = value.arxivURL
        pdfURL = value.pdfURL
        topicIDs = value.topicIDs
        subtopicIDs = value.subtopicIDs
        relevance = value.relevance
        novelty = value.novelty
        capturedAt = value.capturedAt
    }
}
