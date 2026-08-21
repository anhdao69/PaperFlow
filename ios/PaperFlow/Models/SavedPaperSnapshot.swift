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
    var heroFigure: String?
    var figureStatusRawValue: String?
    var topicAssignmentsData: Data?
    var capturedAt: Date

    var figureStatus: FigureStatus {
        figureStatusRawValue.flatMap(FigureStatus.init(rawValue:)) ?? .notImplemented
    }

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
        heroFigure = paper.heroFigure
        figureStatusRawValue = paper.figureStatus.rawValue
        topicAssignmentsData = try? JSONEncoder().encode(paper.topicAssignments)
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
        heroFigure = value.heroFigure
        figureStatusRawValue = value.figureStatusRawValue
        topicAssignmentsData = value.topicAssignmentsData
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
        heroFigure = paper.heroFigure
        figureStatusRawValue = paper.figureStatus.rawValue
        topicAssignmentsData = try? JSONEncoder().encode(paper.topicAssignments)
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
        heroFigure = value.heroFigure
        figureStatusRawValue = value.figureStatusRawValue
        topicAssignmentsData = value.topicAssignmentsData
        capturedAt = value.capturedAt
    }

    func publicPaper() -> PublicPaper {
        let assignments = topicAssignmentsData
            .flatMap { try? JSONDecoder().decode([TopicAssignment].self, from: $0) }
            ?? topicIDs.enumerated().map { index, topicID in
                TopicAssignment(topicId: topicID, subtopicIds: index == 0 ? subtopicIDs : [])
            }
        let savedTLDR = displaySummary == abstract ? nil : displaySummary
        return PublicPaper(
            arxivId: canonicalArxivID,
            title: title,
            authors: authors,
            abstract: abstract,
            arxivUrl: arxivURL,
            pdfUrl: pdfURL,
            firstSeenAt: capturedAt,
            categories: [],
            relevance: relevance,
            novelty: novelty,
            topicAssignments: assignments,
            selectionReason: "Saved for deep reading.",
            tldr: savedTLDR,
            bullets: [],
            summaryStatus: savedTLDR == nil ? .failed : .generated,
            heroFigure: heroFigure,
            figureStatus: figureStatus
        )
    }
}
