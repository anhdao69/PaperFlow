import SwiftData
import SwiftUI

@main
struct PaperFlowApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootTabView(model: model)
                .task { await model.loadFixtureShellIfNeeded() }
        }
        .modelContainer(for: [PersonalPaperState.self, SavedPaperSnapshot.self])
    }
}
