import Foundation

enum PaperDetailSummaryPresentation: Equatable {
    case generated(tldr: String, bullets: [String])
    case abstractFallback
}

enum PaperDetailFigurePresentation: Equatable {
    case placeholder
    case failed
    case ready(relativePath: String)
}

enum PaperDetailViewModel {
    static func summary(for paper: PublicPaper) -> PaperDetailSummaryPresentation {
        if paper.summaryStatus == .generated, let tldr = paper.tldr {
            return .generated(tldr: tldr, bullets: paper.bullets)
        }
        return .abstractFallback
    }

    static func figure(for paper: PublicPaper) -> PaperDetailFigurePresentation {
        switch paper.figureStatus {
        case .notImplemented:
            .placeholder
        case .failed:
            .failed
        case .ready:
            paper.heroFigure.map(PaperDetailFigurePresentation.ready) ?? .failed
        }
    }

    static func topicLabels(for paper: PublicPaper, topics: TopicsIndex?) -> [String] {
        let topicsByID = Dictionary(uniqueKeysWithValues: (topics?.topics ?? []).map { ($0.id, $0) })
        return paper.topicAssignments.flatMap { assignment in
            let topic = topicsByID[assignment.topicId]
            let topicName = topic?.name ?? assignment.topicId
            let subtopics = Dictionary(uniqueKeysWithValues: (topic?.subtopics ?? []).map { ($0.id, $0.name) })
            return [topicName] + assignment.subtopicIds.map { subtopics[$0] ?? $0 }
        }
    }
}
