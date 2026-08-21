import SwiftUI

struct TopicSwipeView: View {
    @Bindable var model: AppModel
    let title: String
    let collectionID: String
    let relativePath: String

    var body: some View {
        Group {
            if let feed = model.topicFeeds[relativePath] {
                DaySwipeView(
                    collectionID: collectionID,
                    collectionTitle: title,
                    papers: feed.days.flatMap(\.papers),
                    topics: model.topicsIndex
                )
            } else if let error = model.topicErrors[relativePath] {
                PFErrorShell(message: error)
            } else {
                PFLoadingShell()
            }
        }
        .background(PFTheme.background)
        .task { await model.loadTopicFeed(relativePath: relativePath) }
    }
}
