import SwiftUI

struct RootTabView: View {
    @Bindable var model: AppModel
    @State private var selection: PaperFlowTab = .today

    var body: some View {
        TabView(selection: $selection) {
            NavigationStack {
                TodayHomeView(model: model)
            }
            .tag(PaperFlowTab.today)
            .tabItem { Label("Today", systemImage: "calendar") }
            .accessibilityIdentifier("tab.today")

            NavigationStack {
                TopicsHomeView(model: model)
            }
            .tag(PaperFlowTab.topics)
            .tabItem { Label("Topics", systemImage: "square.grid.2x2") }
            .accessibilityIdentifier("tab.topics")

            NavigationStack {
                SavedHomeView(model: model) { selection = .today }
            }
            .tag(PaperFlowTab.saved)
            .tabItem { Label("Saved", systemImage: "bookmark") }
            .accessibilityIdentifier("tab.saved")
        }
        .tint(PFTheme.primary)
        .accessibilityIdentifier("root.tabs")
    }
}

private enum PaperFlowTab: Hashable {
    case today
    case topics
    case saved
}
