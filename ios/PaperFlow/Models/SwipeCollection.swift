import Foundation

struct SwipeCollection: Identifiable, Sendable {
    let id: String
    let title: String
    let papers: [PublicPaper]
}

enum SwipeReviewMode: String, CaseIterable, Identifiable {
    case unreviewed = "Unreviewed"
    case all = "All Papers"

    var id: Self { self }
}

enum SwipeDecision: Equatable, Sendable {
    case skip
    case save
}

@MainActor
protocol SwipeFeedback: AnyObject {
    func crossedThreshold(for decision: SwipeDecision)
    func committed(_ decision: SwipeDecision)
}

@MainActor
final class NoOpSwipeFeedback: SwipeFeedback {
    func crossedThreshold(for decision: SwipeDecision) {}
    func committed(_ decision: SwipeDecision) {}
}
