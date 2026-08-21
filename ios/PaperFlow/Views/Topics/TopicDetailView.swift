import SwiftUI

struct TopicDetailView: View {
    @Bindable var model: AppModel
    let topic: PublicTopic

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                    Text(topic.name).font(.largeTitle.bold())
                    Text(paperCountLabel(topic.paperCount))
                        .foregroundStyle(PFTheme.textSecondary)
                        .monospacedDigit()
                }

                NavigationLink {
                    TopicBrowseView(model: model, topic: topic)
                } label: {
                    row(title: "All papers in this topic", count: topic.paperCount)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("topic.browse.all")

                if !topic.subtopics.isEmpty {
                    PFSectionHeader(title: "Subtopics", count: topic.subtopics.count)
                    ForEach(topic.subtopics) { subtopic in
                        NavigationLink {
                            SubtopicBrowseView(model: model, topic: topic, subtopic: subtopic)
                        } label: {
                            row(title: subtopic.name, count: subtopic.paperCount)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("subtopic.row.\(subtopic.id)")
                    }
                }

                HStack {
                    NavigationLink {
                        TopicBrowseView(model: model, topic: topic)
                    } label: {
                        Label("Browse All", systemImage: "list.bullet")
                            .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
                    }
                    .accessibilityIdentifier("topic.browse")
                    NavigationLink {
                        TopicSwipeView(
                            model: model,
                            title: topic.name,
                            collectionID: "topic-\(topic.id)",
                            relativePath: topic.feedUrl
                        )
                    } label: {
                        Label("Swipe Unread", systemImage: "rectangle.stack")
                            .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
                    }
                    .accessibilityIdentifier("topic.swipe")
                }
                .buttonStyle(.borderedProminent)
                .tint(PFTheme.primary)
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationTitle(topic.name)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func row(title: String, count: Int) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                Text(title).font(.headline)
                Text(paperCountLabel(count)).font(.caption).foregroundStyle(PFTheme.textSecondary)
            }
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(PFTheme.textTertiary)
        }
        .frame(minHeight: 58)
        .padding(.horizontal, PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
    }

    private func paperCountLabel(_ count: Int) -> String {
        "\(count) \(count == 1 ? "paper" : "papers")"
    }
}
