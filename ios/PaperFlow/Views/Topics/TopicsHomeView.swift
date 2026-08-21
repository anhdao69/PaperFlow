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
                    HStack(spacing: PFTheme.Spacing.standard) {
                        Image(systemName: "books.vertical.fill")
                            .font(.title2)
                            .foregroundStyle(PFTheme.primary)
                            .frame(width: 48, height: 48)
                            .background(PFTheme.primarySoft, in: .circle)
                        let total = TopicsViewModel.uniqueTotal(index)
                        VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                            Text("Total Papers")
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(PFTheme.textSecondary)
                            Text("\(total)")
                                .font(.title.bold())
                                .foregroundStyle(PFTheme.textPrimary)
                                .monospacedDigit()
                            Text(total == 1 ? "paper in your research library" : "papers in your research library")
                                .font(.caption)
                                .foregroundStyle(PFTheme.textTertiary)
                        }
                    }
                    .padding(PFTheme.Spacing.standard)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.feature))
                    .overlay {
                        RoundedRectangle(cornerRadius: PFTheme.Radius.feature)
                            .stroke(PFTheme.primary.opacity(0.14), lineWidth: 1)
                    }
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
