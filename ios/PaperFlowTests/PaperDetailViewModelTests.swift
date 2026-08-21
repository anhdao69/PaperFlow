import XCTest
@testable import PaperFlow

final class PaperDetailViewModelTests: XCTestCase {
    func testGeneratedSummaryShowsTLDRAndKeyPoints() {
        let paper = detailPaper(
            summaryStatus: .generated,
            tldr: "A concise result.",
            bullets: ["One", "Two", "Three"],
            figureStatus: .notImplemented,
            heroFigure: nil
        )

        XCTAssertEqual(
            PaperDetailViewModel.summary(for: paper),
            .generated(tldr: "A concise result.", bullets: ["One", "Two", "Three"])
        )
        XCTAssertEqual(PaperDetailViewModel.figure(for: paper), .placeholder)
    }

    func testFailedSummaryUsesRequiredAbstractFallback() {
        let paper = detailPaper(
            summaryStatus: .failed,
            tldr: nil,
            bullets: [],
            figureStatus: .failed,
            heroFigure: nil
        )

        XCTAssertEqual(PaperDetailViewModel.summary(for: paper), .abstractFallback)
        XCTAssertFalse(paper.abstract.isEmpty)
        XCTAssertEqual(PaperDetailViewModel.figure(for: paper), .failed)
    }

    func testReadyFigureAndDynamicTopicLabelsUsePublishedValues() {
        let paper = detailPaper(
            summaryStatus: .failed,
            tldr: nil,
            bullets: [],
            figureStatus: .ready,
            heroFigure: "figures/2608.12345/hero.webp"
        )
        let topics = TopicsIndex(
            schemaVersion: 1,
            taxonomyVersion: 1,
            totalPaperCount: 1,
            topics: [
                PublicTopic(
                    id: "dynamic-topic",
                    name: "Dynamic Topic",
                    paperCount: 1,
                    feedUrl: "data/topic.json",
                    subtopics: [
                        PublicSubtopic(
                            id: "dynamic-subtopic",
                            name: "Dynamic Subtopic",
                            paperCount: 1,
                            feedUrl: "data/subtopic.json"
                        )
                    ]
                )
            ]
        )

        XCTAssertEqual(
            PaperDetailViewModel.figure(for: paper),
            .ready(relativePath: "figures/2608.12345/hero.webp")
        )
        XCTAssertEqual(
            PaperDetailViewModel.topicLabels(for: paper, topics: topics),
            ["Dynamic Topic", "Dynamic Subtopic"]
        )
    }

    private func detailPaper(
        summaryStatus: SummaryStatus,
        tldr: String?,
        bullets: [String],
        figureStatus: FigureStatus,
        heroFigure: String?
    ) -> PublicPaper {
        PublicPaper(
            arxivId: "2608.12345",
            title: "Detailed Paper",
            authors: ["Test Author"],
            abstract: "The complete original abstract is always available.",
            arxivUrl: URL(string: "https://arxiv.org/abs/2608.12345")!,
            pdfUrl: URL(string: "https://arxiv.org/pdf/2608.12345")!,
            firstSeenAt: Date(timeIntervalSince1970: 100),
            categories: ["cs.AI"],
            relevance: 9,
            novelty: 8,
            topicAssignments: [
                TopicAssignment(topicId: "dynamic-topic", subtopicIds: ["dynamic-subtopic"])
            ],
            selectionReason: "It is relevant.",
            tldr: tldr,
            bullets: bullets,
            summaryStatus: summaryStatus,
            heroFigure: heroFigure,
            figureStatus: figureStatus
        )
    }
}
