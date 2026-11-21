// The next interview question after the onboarding. The chat asks it in words; the plan screen
// shows the same question as choice cards, and a card simply sends its answer to the chat.
import type { Scenario } from '../types'

export interface Choice {
  /** Card label. */
  label: string
  hint: string
  /** What the card sends to the assistant. */
  prompt: string
  /** Which illustration the card shows. */
  image: 'rest' | 'work'
}

export interface NextQuestion {
  /** Question in the chat greeting, lower case: it follows "Kolejne pytanie:". */
  question: string
  /** Suggestion chips in the chat. */
  prompts: string[]
  /** Heading of the decision cards, or null when this question has no cards. */
  title: string | null
  choices: Choice[]
}

/** The next interview question, worded for whoever is writing. */
export function nextQuestion(scenario: Scenario): NextQuestion {
  const mother = scenario.role === 'mother'
  if (scenario.leave_before_birth_weeks === null && scenario.child_born) {
    return {
      question: mother
        ? 'czy byłaś na urlopie macierzyńskim przed porodem?'
        : 'czy mama była na urlopie macierzyńskim przed porodem?',
      prompts: [
        'Nie, urlop zaczął się w dniu porodu',
        'Tak, 2 tygodnie przed porodem',
        'Kiedy kończy się urlop macierzyński?',
      ],
      title: mother
        ? 'Czy byłaś na urlopie przed porodem?'
        : 'Czy mama była na urlopie przed porodem?',
      choices: [
        {
          label: 'Tak, przed porodem',
          hint: 'urlop zaczął się wcześniej',
          prompt: mother
            ? 'Tak, byłam na urlopie przed porodem'
            : 'Tak, mama była na urlopie przed porodem',
          image: 'rest',
        },
        {
          label: 'Nie, od porodu',
          hint: 'urlop od dnia porodu',
          prompt: 'Nie, urlop zaczął się w dniu porodu',
          image: 'work',
        },
      ],
    }
  }
  if (scenario.leave_before_birth_weeks === null) {
    return {
      question: mother
        ? 'chcesz zacząć urlop macierzyński przed porodem, czy pracować do dnia porodu?'
        : 'czy mama chce zacząć urlop macierzyński przed porodem, czy pracować do dnia porodu?',
      prompts: mother
        ? [
            'Chcę urlop przed porodem',
            'Będę pracować do dnia porodu',
            'Od kiedy najwcześniej mogę zacząć urlop?',
          ]
        : [
            'Mama chce urlop przed porodem',
            'Mama będzie pracować do porodu',
            'Od kiedy najwcześniej może zacząć urlop?',
          ],
      title: mother ? 'Co wybierasz?' : 'Co wybiera mama?',
      choices: [
        {
          label: 'Urlop przed porodem',
          hint: 'odpoczynek przed porodem',
          prompt: mother ? 'Chcę urlop przed porodem' : 'Mama chce urlop przed porodem',
          image: 'rest',
        },
        {
          label: 'Praca do porodu',
          hint: 'urlop od dnia porodu',
          prompt: mother ? 'Będę pracować do dnia porodu' : 'Mama będzie pracować do porodu',
          image: 'work',
        },
      ],
    }
  }
  return {
    question: 'o który element osi chcesz zapytać?',
    prompts: ['Kiedy kończy się urlop macierzyński?', 'Co oznacza 14 tygodni po porodzie?'],
    title: null,
    choices: [],
  }
}
