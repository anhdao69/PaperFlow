import Foundation

@MainActor
protocol PersonalPaperStore: AnyObject {
    func state(for canonicalArxivID: String) throws -> PersonalPaperState?
    func allStates() throws -> [PersonalPaperState]
    func insert(_ state: PersonalPaperState)
    func insert(_ snapshot: SavedPaperSnapshot)
    func delete(_ state: PersonalPaperState)
    func delete(_ snapshot: SavedPaperSnapshot)
    func commit() throws
    func rollback()
}

enum PersonalPaperStoreError: Error, Equatable {
    case duplicateCanonicalID(String)
}
