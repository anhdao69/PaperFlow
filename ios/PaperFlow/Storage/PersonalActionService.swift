import Foundation

@MainActor
final class PersonalActionService {
    typealias Clock = @MainActor () -> Date

    private let store: any PersonalPaperStore
    private let clock: Clock
    private(set) var undoSnapshot: SwipeUndoSnapshot?

    init(store: any PersonalPaperStore, clock: @escaping Clock = Date.init) {
        self.store = store
        self.clock = clock
    }

    @discardableResult
    func save(_ paper: PublicPaper, registersUndo: Bool = false) throws -> PersonalPaperState {
        let canonicalID = PublicPaper.normalizeArxivID(paper.arxivId)
        let prior = try store.state(for: canonicalID).map(PersonalPaperStateValue.init)
        let state = try existingOrNewState(canonicalID)
        let now = clock()

        state.seen = true
        state.lastSeenAt = now
        if !state.saved {
            state.saved = true
            if state.savedAt == nil {
                state.savedAt = now
            }
            state.lastSavedAt = now
            state.unsavedAt = nil
            if state.readingStatus == nil {
                state.readingStatus = .queue
                state.statusChangedAt = now
            }
        }
        if state.snapshot == nil {
            let snapshot = SavedPaperSnapshot(paper: paper, capturedAt: now)
            store.insert(snapshot)
            state.snapshot = snapshot
        }

        try commitOrRollback()
        if registersUndo {
            undoSnapshot = SwipeUndoSnapshot(canonicalArxivID: canonicalID, priorState: prior)
        }
        return state
    }

    @discardableResult
    func skip(arxivID: String, registersUndo: Bool = false) throws -> PersonalPaperState {
        let canonicalID = PublicPaper.normalizeArxivID(arxivID)
        let prior = try store.state(for: canonicalID).map(PersonalPaperStateValue.init)
        let state = try existingOrNewState(canonicalID)
        state.seen = true
        state.lastSeenAt = clock()
        try commitOrRollback()
        if registersUndo {
            undoSnapshot = SwipeUndoSnapshot(canonicalArxivID: canonicalID, priorState: prior)
        }
        return state
    }

    @discardableResult
    func unsave(arxivID: String) throws -> PersonalPaperState? {
        guard let state = try store.state(for: arxivID), state.saved else { return nil }
        state.saved = false
        state.unsavedAt = clock()
        try commitOrRollback()
        return state
    }

    @discardableResult
    func transition(arxivID: String, to status: ReadingStatus) throws -> PersonalPaperState {
        guard let state = try store.state(for: arxivID), state.saved else {
            throw PersonalStateError.missingSavedState
        }
        let now = clock()
        if state.readingStatus != status {
            state.readingStatus = status
            state.statusChangedAt = now
            switch status {
            case .queue:
                state.completedAt = nil
            case .reading:
                state.startedReadingAt = now
                state.completedAt = nil
            case .done:
                state.completedAt = now
            }
        }
        try commitOrRollback()
        return state
    }

    @discardableResult
    func markOpened(arxivID: String) throws -> PersonalPaperState? {
        guard let state = try store.state(for: arxivID), state.saved else { return nil }
        state.lastOpenedAt = clock()
        try commitOrRollback()
        return state
    }

    @discardableResult
    func updateNote(arxivID: String, note: String) throws -> PersonalPaperState {
        guard let state = try store.state(for: arxivID), state.saved else {
            throw PersonalStateError.missingSavedState
        }
        state.note = note
        try commitOrRollback()
        return state
    }

    @discardableResult
    func updateRating(arxivID: String, rating: Int?) throws -> PersonalPaperState {
        if let rating, !(1 ... 5).contains(rating) {
            throw PersonalStateError.invalidRating
        }
        guard let state = try store.state(for: arxivID), state.saved else {
            throw PersonalStateError.missingSavedState
        }
        state.rating = rating
        try commitOrRollback()
        return state
    }

    func refreshSnapshot(with paper: PublicPaper) throws {
        guard let state = try store.state(for: paper.arxivId), let snapshot = state.snapshot else {
            return
        }
        snapshot.refresh(from: paper, capturedAt: clock())
        try commitOrRollback()
    }

    @discardableResult
    func undoLastAction() throws -> PersonalPaperState? {
        guard let undoSnapshot else { throw PersonalStateError.missingUndo }
        let current = try store.state(for: undoSnapshot.canonicalArxivID)
        let restored: PersonalPaperState?
        if let prior = undoSnapshot.priorState {
            let state = try current ?? existingOrNewState(prior.canonicalArxivID)
            restore(state, from: prior)
            restored = state
        } else {
            if let current { store.delete(current) }
            restored = nil
        }
        try commitOrRollback()
        self.undoSnapshot = nil
        return restored
    }

    private func existingOrNewState(_ canonicalID: String) throws -> PersonalPaperState {
        if let existing = try store.state(for: canonicalID) { return existing }
        let state = PersonalPaperState(canonicalArxivID: canonicalID)
        store.insert(state)
        return state
    }

    private func restore(_ state: PersonalPaperState, from value: PersonalPaperStateValue) {
        state.seen = value.seen
        state.lastSeenAt = value.lastSeenAt
        state.saved = value.saved
        state.savedAt = value.savedAt
        state.lastSavedAt = value.lastSavedAt
        state.unsavedAt = value.unsavedAt
        state.readingStatus = value.readingStatus
        state.statusChangedAt = value.statusChangedAt
        state.startedReadingAt = value.startedReadingAt
        state.completedAt = value.completedAt
        state.lastOpenedAt = value.lastOpenedAt
        state.note = value.note
        state.rating = value.rating
        if let snapshotValue = value.snapshot {
            if let snapshot = state.snapshot {
                snapshot.restore(snapshotValue)
            } else {
                let snapshot = SavedPaperSnapshot(value: snapshotValue)
                store.insert(snapshot)
                state.snapshot = snapshot
            }
        } else if let snapshot = state.snapshot {
            state.snapshot = nil
            store.delete(snapshot)
        }
    }

    private func commitOrRollback() throws {
        do {
            try store.commit()
        } catch {
            store.rollback()
            throw error
        }
    }
}
