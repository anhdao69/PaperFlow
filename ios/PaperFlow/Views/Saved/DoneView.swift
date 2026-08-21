import SwiftUI

struct DoneView: View {
    @Bindable var model: AppModel

    var body: some View {
        SavedCollectionView(model: model, status: .done)
    }
}
