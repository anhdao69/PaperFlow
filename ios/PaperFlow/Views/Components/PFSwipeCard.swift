import SwiftUI

struct PFSwipeCard: View {
    let paper: PublicPaper
    let topicLabels: [String]
    let feedback: any SwipeFeedback
    let onDecision: (SwipeDecision) -> Void
    let onOpenDetail: () -> Void

    @State private var offset: CGSize = .zero
    @State private var crossedDecision: SwipeDecision?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    private let threshold: CGFloat = 105

    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
            PFFigurePlaceholder(status: paper.figureStatus, height: 210)
            Text(paper.title)
                .font(.title2.bold())
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? nil : 3)
                .fixedSize(horizontal: false, vertical: true)
            if !topicLabels.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack { ForEach(topicLabels, id: \.self) { PFTag(text: $0) } }
                }
            }
            Text(paper.displaySummary)
                .font(.body)
                .foregroundStyle(PFTheme.textSecondary)
                .lineLimit(4)
            HStack {
                PFTag(text: "Relevance \(paper.relevance)")
                PFTag(text: "Novelty \(paper.novelty)")
            }
        }
        .padding(PFTheme.Spacing.standard)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(cardBackground, in: .rect(cornerRadius: PFTheme.Radius.feature))
        .overlay(alignment: offset.width >= 0 ? .topLeading : .topTrailing) {
            decisionOverlay
        }
        .overlay {
            RoundedRectangle(cornerRadius: PFTheme.Radius.feature)
                .stroke(PFTheme.divider.opacity(0.45), lineWidth: 0.5)
        }
        .contentShape(.rect)
        .onTapGesture(perform: onOpenDetail)
        .offset(offset)
        .rotationEffect(.degrees(PFMotionPolicy.rotation(
            Double(offset.width / 24).clamped(to: -7 ... 7),
            reduceMotion: reduceMotion
        )))
        .gesture(
            DragGesture(minimumDistance: 8)
                .onChanged(handleDrag)
                .onEnded(handleEnd)
        )
        .animation(PFMotionPolicy.animation(reduceMotion: reduceMotion), value: offset)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("swipe.card.\(paper.arxivId)")
    }

    private var decision: SwipeDecision? {
        if offset.width >= threshold { return .save }
        if offset.width <= -threshold { return .skip }
        return nil
    }

    private var cardBackground: Color {
        guard abs(offset.width) > 12 else { return PFTheme.surface }
        return offset.width > 0 ? PFTheme.successSoft : PFTheme.dangerSoft
    }

    @ViewBuilder
    private var decisionOverlay: some View {
        if abs(offset.width) > 30 {
            Label(
                offset.width > 0 ? "SAVE" : "SKIP",
                systemImage: offset.width > 0 ? "bookmark.fill" : "xmark"
            )
            .font(.headline.bold())
            .foregroundStyle(offset.width > 0 ? PFTheme.success : PFTheme.danger)
            .padding(PFTheme.Spacing.standard)
            .opacity(min(abs(offset.width) / threshold, 1))
        }
    }

    private func handleDrag(_ value: DragGesture.Value) {
        offset = CGSize(width: value.translation.width, height: value.translation.height * 0.12)
        let newDecision = decision
        if newDecision != crossedDecision, let newDecision {
            feedback.crossedThreshold(for: newDecision)
        }
        crossedDecision = newDecision
    }

    private func handleEnd(_ value: DragGesture.Value) {
        guard let decision else {
            offset = .zero
            crossedDecision = nil
            return
        }
        offset.width = decision == .save ? 700 : -700
        onDecision(decision)
        offset = .zero
        crossedDecision = nil
    }
}

private extension Comparable {
    func clamped(to limits: ClosedRange<Self>) -> Self {
        min(max(self, limits.lowerBound), limits.upperBound)
    }
}
