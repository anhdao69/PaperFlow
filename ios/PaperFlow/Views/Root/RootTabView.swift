import SwiftUI

struct RootTabView: View {
    @Bindable var model: AppModel

    var body: some View {
        TabView {
            NavigationStack {
                TodayRootView(model: model)
            }
            .tabItem { Label("Today", systemImage: "calendar") }
            .accessibilityIdentifier("tab.today")

            NavigationStack {
                TopicsRootView(model: model)
            }
            .tabItem { Label("Topics", systemImage: "square.grid.2x2") }
            .accessibilityIdentifier("tab.topics")

            NavigationStack {
                SavedRootView()
            }
            .tabItem { Label("Saved", systemImage: "bookmark") }
            .accessibilityIdentifier("tab.saved")
        }
        .tint(PFTheme.primary)
        .accessibilityIdentifier("root.tabs")
    }
}

private struct TodayRootView: View {
    @Bindable var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                    Text("PaperFlow")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(PFTheme.primary)
                    Text("Today")
                        .font(.largeTitle.bold())
                }
                stateContent
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.today")
    }

    @ViewBuilder
    private var stateContent: some View {
        switch model.loadState {
        case .idle, .loading:
            PFLoadingShell()
        case let .failed(message):
            PFErrorShell(message: message)
        case .loaded:
            if let feed = model.dailyFeed {
                VStack(alignment: .leading, spacing: PFTheme.Spacing.standard) {
                    PFSectionHeader(title: "Today’s Papers", count: feed.paperCount)
                    PFProgressView(reviewed: 0, total: feed.paperCount)
                    if let first = feed.papers.first {
                        PFPaperListCard(paper: first)
                    } else {
                        PFEmptyShell(
                            title: "No papers today",
                            message: "No papers matched the configured research interests."
                        )
                    }
                    PFPrimaryButton(
                        title: "Browse Papers",
                        systemImage: "list.bullet",
                        accessibilityIdentifier: "today.browse"
                    ) {}
                }
            } else {
                PFEmptyShell(
                    title: "Today’s feed isn’t available yet",
                    message: "Check again after the next PaperFlow publication."
                )
            }
        }
    }
}

private struct TopicsRootView: View {
    @Bindable var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                Text("Topics")
                    .font(.largeTitle.bold())
                if let topics = model.topicsIndex {
                    LazyVStack(spacing: PFTheme.Spacing.medium) {
                        ForEach(topics.topics) { topic in
                            HStack(spacing: PFTheme.Spacing.medium) {
                                Image(systemName: "square.grid.2x2.fill")
                                    .foregroundStyle(PFTheme.primary)
                                    .frame(width: PFTheme.minimumTapTarget)
                                VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                                    Text(topic.name)
                                        .font(.headline)
                                    Text("\(topic.paperCount) papers · \(topic.subtopics.count) subtopics")
                                        .font(.caption)
                                        .foregroundStyle(PFTheme.textSecondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .foregroundStyle(PFTheme.textTertiary)
                            }
                            .frame(minHeight: PFTheme.minimumTapTarget)
                            .padding(PFTheme.Spacing.standard)
                            .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
                            .accessibilityElement(children: .combine)
                            .accessibilityIdentifier("topic.row.\(topic.id)")
                        }
                    }
                } else if model.loadState == .loading || model.loadState == .idle {
                    PFLoadingShell()
                } else {
                    PFEmptyShell(title: "No topics", message: "Topic data is unavailable.")
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.topics")
    }
}

private struct SavedRootView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                Text("Saved")
                    .font(.largeTitle.bold())
                PFEmptyShell(
                    title: "No saved papers yet",
                    message: "Papers you save while reviewing will appear here."
                )
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.saved")
    }
}
