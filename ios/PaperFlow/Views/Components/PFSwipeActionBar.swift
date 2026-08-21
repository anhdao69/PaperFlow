import SwiftUI
import UIKit

@MainActor
final class UIKitSwipeFeedback: SwipeFeedback {
    private let thresholdGenerator = UISelectionFeedbackGenerator()

    func crossedThreshold(for decision: SwipeDecision) {
        thresholdGenerator.selectionChanged()
        thresholdGenerator.prepare()
    }

    func committed(_ decision: SwipeDecision) {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
    }
}

struct PFSwipeActionBar: View {
    let canUndo: Bool
    let onSkip: () -> Void
    let onUndo: () -> Void
    let onSave: () -> Void

    var body: some View {
        HStack(spacing: PFTheme.Spacing.large) {
            actionButton(
                title: "Skip",
                image: "xmark",
                color: PFTheme.danger,
                background: PFTheme.dangerSoft,
                identifier: "swipe.skip",
                action: onSkip
            )
            actionButton(
                title: "Undo",
                image: "arrow.uturn.backward",
                color: PFTheme.textSecondary,
                background: PFTheme.surfaceSecondary,
                identifier: "swipe.undo",
                action: onUndo
            )
            .disabled(!canUndo)
            actionButton(
                title: "Save",
                image: "bookmark.fill",
                color: PFTheme.success,
                background: PFTheme.successSoft,
                identifier: "swipe.save",
                action: onSave
            )
        }
        .frame(maxWidth: .infinity)
    }

    private func actionButton(
        title: String,
        image: String,
        color: Color,
        background: Color,
        identifier: String,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(spacing: PFTheme.Spacing.xSmall) {
                Image(systemName: image).font(.title2.bold())
                Text(title).font(.caption.weight(.semibold))
            }
            .foregroundStyle(color)
            .frame(maxWidth: .infinity, minHeight: 64)
            .background(background, in: .rect(cornerRadius: PFTheme.Radius.card))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(identifier)
    }
}
