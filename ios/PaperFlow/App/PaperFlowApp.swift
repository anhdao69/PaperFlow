import SwiftUI

@main
struct PaperFlowApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootTabView(model: model)
                .task { await model.loadFixtureShellIfNeeded() }
        }
    }
}
