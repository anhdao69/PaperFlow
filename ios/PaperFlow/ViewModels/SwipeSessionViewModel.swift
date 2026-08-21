import Foundation
import Observation

enum SwipeSessionError: Error, Equatable {
    case noEligiblePaper
    case noActionToUndo
}

@MainActor
@Observable
final class SwipeSessionViewModel {
    let collection: SwipeCollection
    var reviewMode: SwipeReviewMode = .unreviewed
    var selectedTopicIDs: Set<String> = []
    private(set) var completedIDs: Set<String> = []
    private(set) var lastActionPaperID: String?
    private(set) var stateVersion = 0

    private let store: any PersonalPaperStore
    private let actions: PersonalActionService
    let feedback: any SwipeFeedback

    init(
        collection: SwipeCollection,
        store: any PersonalPaperStore,
        actions: PersonalActionService? = nil,
        feedback: (any SwipeFeedback)? = nil
    ) {
        self.collection = collection
        self.store = store
        self.actions = actions ?? PersonalActionService(store: store)
        self.feedback = feedback ?? NoOpSwipeFeedback()
    }

    var activePapers: [PublicPaper] {
        guard !selectedTopicIDs.isEmpty else { return collection.papers }
        return collection.papers.filter { paper in
            paper.topicAssignments.contains { selectedTopicIDs.contains($0.topicId) }
        }
    }

    var currentPaper: PublicPaper? {
        let stateByID = personalStateByID
        return activePapers.first { paper in
            let id = PublicPaper.normalizeArxivID(paper.arxivId)
            guard !completedIDs.contains(id) else { return false }
            switch reviewMode {
            case .unreviewed:
                return stateByID[id]?.seen != true
            case .all:
                return true
            }
        }
    }

    var progress: CollectionProgress {
        let stateByID = personalStateByID
        let reviewed = activePapers.reduce(into: 0) { count, paper in
            if stateByID[PublicPaper.normalizeArxivID(paper.arxivId)]?.seen == true {
                count += 1
            }
        }
        return CollectionProgress(reviewed: reviewed, total: activePapers.count)
    }

    var remainingSessionCount: Int {
        let stateByID = personalStateByID
        return activePapers.reduce(into: 0) { count, paper in
            let id = PublicPaper.normalizeArxivID(paper.arxivId)
            guard !completedIDs.contains(id) else { return }
            if reviewMode == .all || stateByID[id]?.seen != true { count += 1 }
        }
    }

    var savedInCollectionCount: Int {
        let stateByID = personalStateByID
        return activePapers.reduce(into: 0) { count, paper in
            if stateByID[PublicPaper.normalizeArxivID(paper.arxivId)]?.saved == true {
                count += 1
            }
        }
    }

    var canUndo: Bool { lastActionPaperID != nil && actions.undoSnapshot != nil }
    var isComplete: Bool { currentPaper == nil }

    func perform(_ decision: SwipeDecision) throws {
        guard let paper = currentPaper else { throw SwipeSessionError.noEligiblePaper }
        switch decision {
        case .skip:
            try actions.skip(arxivID: paper.arxivId, registersUndo: true)
        case .save:
            try actions.save(paper, registersUndo: true)
        }
        let id = PublicPaper.normalizeArxivID(paper.arxivId)
        completedIDs.insert(id)
        lastActionPaperID = id
        stateVersion += 1
        feedback.committed(decision)
    }

    func undo() throws {
        guard let lastActionPaperID, canUndo else {
            throw SwipeSessionError.noActionToUndo
        }
        _ = try actions.undoLastAction()
        completedIDs.remove(lastActionPaperID)
        self.lastActionPaperID = nil
        stateVersion += 1
    }

    func synchronizePersonalState() {
        stateVersion += 1
    }

    private var personalStateByID: [String: PersonalPaperState] {
        let states = (try? store.allStates()) ?? []
        return Dictionary(uniqueKeysWithValues: states.map { ($0.canonicalArxivID, $0) })
    }
}
