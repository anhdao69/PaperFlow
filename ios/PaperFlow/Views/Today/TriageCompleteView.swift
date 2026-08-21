import SwiftUI

struct TriageCompleteView: View {
    let progress: CollectionProgress
    let savedCount: Int
    let canUndo: Bool
    let onUndo: () -> Void

    var body: some View {
        VStack(spacing: PFTheme.Spacing.large) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 58))
                .foregroundStyle(PFTheme.success)
            Text("All caught up!")
                .font(.title.bold())
            Text("You’ve reviewed every eligible paper in this collection.")
                .multilineTextAlignment(.center)
                .foregroundStyle(PFTheme.textSecondary)
            HStack(spacing: PFTheme.Spacing.large) {
                metric(progress.reviewed, "Reviewed")
                metric(savedCount, "Saved")
                metric(progress.percentage, "Complete", suffix: "%")
            }
            if canUndo {
                Button("Undo Last Action", systemImage: "arrow.uturn.backward", action: onUndo)
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("swipe.complete.undo")
            }
        }
        .frame(maxWidth: .infinity, minHeight: 420)
        .padding(PFTheme.Spacing.large)
        .accessibilityIdentifier("swipe.complete")
    }

    private func metric(_ value: Int, _ label: String, suffix: String = "") -> some View {
        VStack(spacing: PFTheme.Spacing.xSmall) {
            Text("\(value)\(suffix)").font(.title3.bold()).monospacedDigit()
            Text(label).font(.caption).foregroundStyle(PFTheme.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}
