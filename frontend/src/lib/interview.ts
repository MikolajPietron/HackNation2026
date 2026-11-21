// The next interview question after the onboarding, as the backend computes it. The chat asks it
// in words; the plan screen shows the same question as choice cards, and a card simply sends its
// answer to the chat.
import type { InterviewQuestion, Scenario } from '../types'

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

/**
 * The next interview question as the backend computes it (the assistant asks the same one), with
 * the suggestion chips and, where the answer is a choice between two paths, the decision cards.
 * Without a question the interview is done.
 */
export function nextQuestion(scenario: Scenario, asked: InterviewQuestion | null): NextQuestion {
  const mother = scenario.role === 'mother'
  const father = scenario.role === 'father'
  const done: NextQuestion = {
    question: 'o który element osi chcesz zapytać?',
    prompts: ['Kiedy kończy się urlop macierzyński?', 'Co oznacza 14 tygodni po porodzie?'],
    title: null,
    choices: [],
  }
  if (!asked) return done
  const ask = (prompts: string[]): NextQuestion => ({
    question: asked.text,
    prompts,
    title: null,
    choices: [],
  })
  switch (asked.key) {
    case 'date':
      return ask(['Podam przewidywaną datę porodu', 'Dziecko już się urodziło'])
    case 'children':
      return ask(['Jedno dziecko', 'Bliźnięta'])
    case 'mother-work':
      return ask(
        mother
          ? ['Pracuję na etacie', 'Mam umowę zlecenia', 'Mam własną firmę', 'Nie pracuję']
          : ['Mama pracuje na etacie', 'Mama ma umowę zlecenia', 'Mama ma własną firmę', 'Mama nie pracuje'],
      )
    case 'mother-insurance':
      return ask(
        mother
          ? ['Tak, jestem zgłoszona', 'Nie jestem zgłoszona']
          : ['Tak, mama jest zgłoszona', 'Nie, mama nie jest zgłoszona'],
      )
    case 'father-work':
      return ask(
        father
          ? ['Pracuję na etacie', 'Mam umowę zlecenia', 'Mam własną firmę', 'Nie pracuję']
          : ['Tata pracuje na etacie', 'Tata ma umowę zlecenia', 'Tata ma własną firmę', 'Tata nie pracuje'],
      )
    case 'father-insurance':
      return ask(
        father
          ? ['Tak, jestem zgłoszony', 'Nie jestem zgłoszony']
          : ['Tak, tata jest zgłoszony', 'Nie, tata nie jest zgłoszony'],
      )
    case 'certificate':
      return ask(
        mother
          ? ['Tak, mam zaświadczenie', 'Jeszcze go nie mam']
          : ['Tak, mama ma zaświadczenie', 'Mama jeszcze go nie ma'],
      )
    case 'hospital':
      return ask(['Nie, urodziło się o czasie i nie było w szpitalu', 'Tak, było w szpitalu'])
    case 'leave-before-birth':
      return leaveBeforeBirth(scenario, asked.text)
    default:
      return ask([])
  }
}

/** The one real choice between two paths: the cards on the plan and the chips in the chat. */
function leaveBeforeBirth(scenario: Scenario, question: string): NextQuestion {
  const mother = scenario.role === 'mother'
  if (scenario.child_born) {
    return {
      question,
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
  return {
    question,
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
