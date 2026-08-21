import SwiftUI

struct TopicsHomeView: View {
    @Bindable var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                Text("Topics").font(.largeTitle.bold())
                if model.isShowingCachedData {
                    PFOfflineIndicator(lastUpdatedAt: model.lastUpdatedAt)
                }
                if let message = model.refreshMessage {
                    PFErrorBanner(message: message) { Task { await model.refresh() } }
                }
                if let index = model.topicsIndex {
                    VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                        Text("Total Papers")
                            .font(.subheadline)
                            .foregroundStyle(PFTheme.textSecondary)
                        let total = TopicsViewModel.uniqueTotal(index)
                        Text("\(total) \(total == 1 ? "paper" : "papers")")
                            .font(.title2.bold())
                            .monospacedDigit()
                    }
                    .padding(PFTheme.Spacing.standard)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(PFTheme.primarySoft, in: .rect(cornerRadius: PFTheme.Radius.feature))
                    .accessibilityIdentifier("topics.total")

                    LazyVStack(spacing: PFTheme.Spacing.small) {
                        ForEach(index.topics) { topic in
                            NavigationLink {
                                TopicDetailView(model: model, topic: topic)
                            } label: {
                                topicRow(topic)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("topic.row.\(topic.id)")
                        }
                    }
                } else if model.loadState == .idle || model.loadState == .loading {
                    PFLoadingShell()
                } else {
                    PFErrorShell(message: "Topic data is unavailable.")
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await model.refresh() }
    }

    private func topicRow(_ topic: PublicTopic) -> some View {
        HStack(spacing: PFTheme.Spacing.medium) {
            Image(systemName: "square.grid.2x2.fill")
                .foregroundStyle(PFTheme.primary)
                .frame(width: PFTheme.minimumTapTarget)
            VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                Text(topic.name).font(.headline)
                Text(
                    "\(topic.paperCount) \(topic.paperCount == 1 ? "paper" : "papers")"
                    + " · \(topic.subtopics.count) \(topic.subtopics.count == 1 ? "subtopic" : "subtopics")"
                )
                    .font(.caption)
                    .foregroundStyle(PFTheme.textSecondary)
            }
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(PFTheme.textTertiary)
        }
        .frame(minHeight: 60)
        .padding(.horizontal, PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
        .accessibilityElement(children: .combine)
    }
}
