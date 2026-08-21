import Foundation
import SwiftData

@MainActor
final class SwiftDataPersonalPaperStore: PersonalPaperStore {
    let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        self.modelContext.autosaveEnabled = false
    }

    convenience init(modelContainer: ModelContainer) {
        self.init(modelContext: ModelContext(modelContainer))
    }

    func state(for canonicalArxivID: String) throws -> PersonalPaperState? {
        let canonicalID = PublicPaper.normalizeArxivID(canonicalArxivID)
        var descriptor = FetchDescriptor<PersonalPaperState>(
            predicate: #Predicate { $0.canonicalArxivID == canonicalID }
        )
        descriptor.fetchLimit = 2
        let matches = try modelContext.fetch(descriptor)
        guard matches.count <= 1 else {
            throw PersonalPaperStoreError.duplicateCanonicalID(canonicalID)
        }
        return matches.first
    }

    func allStates() throws -> [PersonalPaperState] {
        try modelContext.fetch(FetchDescriptor<PersonalPaperState>())
    }

    func insert(_ state: PersonalPaperState) {
        modelContext.insert(state)
    }

    func insert(_ snapshot: SavedPaperSnapshot) {
        modelContext.insert(snapshot)
    }

    func delete(_ state: PersonalPaperState) {
        modelContext.delete(state)
    }

    func delete(_ snapshot: SavedPaperSnapshot) {
        modelContext.delete(snapshot)
    }

    func commit() throws {
        try modelContext.save()
    }

    func rollback() {
        modelContext.rollback()
    }
}
