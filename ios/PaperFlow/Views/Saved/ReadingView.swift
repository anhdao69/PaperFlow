import SwiftUI

struct ReadingView: View {
    @Bindable var model: AppModel

    var body: some View {
        SavedCollectionView(model: model, status: .reading)
    }
}
