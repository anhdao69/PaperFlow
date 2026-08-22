import SwiftUI

struct PFSwipeCard: View {
    let paper: PublicPaper
    let topicLabels: [String]
    let feedback: any SwipeFeedback
    let onDecision: (SwipeDecision) -> Void
    let onOpenDetail: () -> Void

    @State private var offset: CGSize = .zero
    @State private var crossedDecision: SwipeDecision?
    @State private var isCommitting = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    private let threshold: CGFloat = 120

    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
            PFFigureView(
                relativePath: paper.heroFigure,
                status: paper.figureStatus,
                height: dynamicTypeSize.isAccessibilitySize ? 240 : 320,
                contentMode: .fit
            )
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
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? nil : 6)
                .lineSpacing(3)
            HStack {
                PFTag(text: "Relevance \(paper.relevance)")
                PFTag(text: "Novelty \(paper.novelty)")
            }
        }
        .padding(PFTheme.Spacing.standard)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
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
        .scaleEffect(isCommitting ? 0.96 : 1)
        .opacity(isCommitting ? 0.15 : 1)
        .rotationEffect(.degrees(PFMotionPolicy.rotation(
            Double(offset.width / 24).clamped(to: -7 ... 7),
            reduceMotion: reduceMotion
        )))
        .gesture(
            DragGesture(minimumDistance: 8)
                .onChanged(handleDrag)
                .onEnded(handleEnd)
        )
        .allowsHitTesting(!isCommitting)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("swipe.card.\(paper.arxivId)")
    }

    private var decision: SwipeDecision? { decision(for: offset.width) }

    private func decision(for width: CGFloat) -> SwipeDecision? {
        if width >= threshold { return .save }
        if width <= -threshold { return .skip }
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
        let projected = decision(for: value.predictedEndTranslation.width)
        guard let decision = decision ?? projected else {
            withAnimation(PFMotionPolicy.animation(reduceMotion: reduceMotion)) {
                offset = .zero
            }
            crossedDecision = nil
            return
        }
        isCommitting = true
        let duration = reduceMotion ? 0.01 : 0.36
        withAnimation(.easeIn(duration: duration)) {
            offset = CGSize(
                width: decision == .save ? 760 : -760,
                height: value.translation.height * 0.35
            )
        }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(duration))
            onDecision(decision)
            offset = .zero
            crossedDecision = nil
            isCommitting = false
        }
    }
}

private extension Comparable {
    func clamped(to limits: ClosedRange<Self>) -> Self {
        min(max(self, limits.lowerBound), limits.upperBound)
    }
}
