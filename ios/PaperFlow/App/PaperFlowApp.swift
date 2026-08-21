import SwiftData
import SwiftUI

@main
struct PaperFlowApp: App {
    @State private var model: AppModel
    private let modelContainer: ModelContainer

    init() {
        let isUITesting = ProcessInfo.processInfo.arguments.contains("--ui-testing")
        let isCachedOfflineFixture = ProcessInfo.processInfo.arguments.contains(
            "--ui-testing-cached-offline"
        )
        _model = State(initialValue: isUITesting
            ? AppModel(
                client: BundledFixtureFeedClient(),
                reportsCachedData: isCachedOfflineFixture
            )
            : AppModel.production()
        )
        let configuration = ModelConfiguration(isStoredInMemoryOnly: isUITesting)
        do {
            modelContainer = try ModelContainer(
                for: PersonalPaperState.self,
                SavedPaperSnapshot.self,
                configurations: configuration
            )
        } catch {
            fatalError("PaperFlow personal storage could not be initialized.")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootTabView(model: model)
                .task { await model.loadFixtureShellIfNeeded() }
        }
        .modelContainer(modelContainer)
    }
}
