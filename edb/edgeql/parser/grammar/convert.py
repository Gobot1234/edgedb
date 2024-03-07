#
# This source file is part of the EdgeDB open source project.
#
# Copyright 2008-present MagicStack Inc. and the EdgeDB authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import parsing
import pathlib
from typing import List, Sequence, Tuple, Dict, Callable


class EBNF_Item:
    pass


class EBNF_Literal(EBNF_Item):
    def __init__(self, token: str):
        self.token = token


class EBNF_Reference(EBNF_Item):
    def __init__(self, name: str):
        self.name = name


class EBNF_Single(EBNF_Item):
    def __init__(self, inner: EBNF_Item):
        self.inner = inner


class EBNF_Optional(EBNF_Single):
    def __init__(self, inner: EBNF_Item):
        super().__init__(inner)


class EBNF_Multiple(EBNF_Item):
    def __init__(self, inner: Sequence[EBNF_Item]):
        self.inner = inner


class EBNF_Sequence(EBNF_Multiple):
    def __init__(self, inner: Sequence[EBNF_Item]):
        super().__init__(inner)


class EBNF_Choice(EBNF_Multiple):
    def __init__(self, inner: Sequence[EBNF_Item]):
        super().__init__(inner)


class EBNF_Production:
    def __init__(self, name: str, item: EBNF_Item):
        self.name = name
        self.item = item


def ebnf_single_or_sequence(items: Sequence[EBNF_Item]) -> EBNF_Item:
    if len(items) == 1:
        return items[0]
    else:
        return EBNF_Sequence(items)


def ebnf_single_or_choice(items: Sequence[EBNF_Item]) -> EBNF_Item:
    if len(items) == 1:
        return items[0]
    else:
        return EBNF_Choice(items)


def expand_iso_ebnf(item: EBNF_Item) -> str:
    match item:
        case EBNF_Literal():
            return '"' + item.token + '"'
        case EBNF_Reference():
            return item.name
        case EBNF_Optional():
            return '[' + expand_iso_ebnf(item.inner) + ']'
        case EBNF_Sequence():
            return (
                '('
                + ', '.join(expand_iso_ebnf(inner) for inner in item.inner)
                + ')'
            )
        case EBNF_Choice():
            return (
                '('
                + ' | '.join(
                    expand_iso_ebnf(inner_item) for inner_item in item.inner
                )
                + ')'
            )
        case _:
            raise NotImplementedError


def to_iso_ebnf(productions: List[EBNF_Production]) -> List[str]:
    return [
        production.name + ' = ' + expand_iso_ebnf(production.item) + ';'
        for production in productions
    ]


def expand_w3c_ebnf(item: EBNF_Item) -> str:
    match item:
        case EBNF_Literal():
            return '"' + item.token + '"'
        case EBNF_Reference():
            return item.name
        case EBNF_Optional():
            return expand_w3c_ebnf(item.inner) + '?'
        case EBNF_Sequence():
            return (
                '('
                + ' '.join(
                    expand_w3c_ebnf(inner_item) for inner_item in item.inner
                )
                + ')'
            )
        case EBNF_Choice():
            return (
                '('
                + ' | '.join(
                    expand_w3c_ebnf(inner_item) for inner_item in item.inner
                )
                + ')'
            )
        case _:
            raise NotImplementedError


def to_w3c_ebnf(productions: List[EBNF_Production]) -> List[str]:
    return [
        production.name + ' ::= ' + expand_w3c_ebnf(production.item)
        for production in productions
    ]


def simplify_productions(
    productions: List[EBNF_Production],
) -> List[EBNF_Production]:

    productions_by_name: Dict[str, EBNF_Production] = {
        production.name: production for production in productions
    }

    def referenced_item(reference: EBNF_Reference) -> EBNF_Item:
        return productions_by_name[reference.name].item

    def is_reference_to(item: EBNF_Item, name: str) -> bool:
        return isinstance(item, EBNF_Reference) and item.name == name

    def is_literal_reference(item: EBNF_Item) -> bool:
        return isinstance(item, EBNF_Reference) and isinstance(
            referenced_item(item), EBNF_Literal
        )

    def is_non_literal_reference(item: EBNF_Item) -> bool:
        return isinstance(item, EBNF_Reference) and not isinstance(
            referenced_item(item), EBNF_Literal
        )

    # remove unused productions

    reference_counts: Dict[str, int] = {
        production.name: 0 for production in productions
    }

    def update_reference_count(prod_name: str, item: EBNF_Item):
        match item:
            case EBNF_Reference():
                if prod_name != item.name:
                    # don't count recursive references
                    reference_counts[item.name] += 1
            case EBNF_Single():
                update_reference_count(prod_name, item.inner)
            case EBNF_Multiple():
                for inner_item in item.inner:
                    update_reference_count(prod_name, inner_item)

    for production in productions:
        update_reference_count(production.name, production.item)

    productions = [
        production
        for production in productions
        if reference_counts[production.name] > 0
    ]

    # utilities to help inlining

    def separate_references_to_inline(
        productions: Sequence[EBNF_Production],
        is_inlined: Callable[[EBNF_Item], bool],
    ):
        inlined_references: Dict[str, EBNF_Item] = {
            production.name: production.item
            for production in productions
            if is_inlined(production.item)
        }
        productions = [
            production
            for production in productions
            if not is_inlined(production.item)
        ]

        return productions, inlined_references

    def inline_references(
        item: EBNF_Item, references: Dict[str, EBNF_Item]
    ) -> Tuple[EBNF_Item, bool]:

        if isinstance(item, EBNF_Reference):
            if item.name in references:
                return references[item.name], True

        return item, False

    # inline direct references

    productions, direct_references = separate_references_to_inline(
        productions, lambda item: isinstance(item, EBNF_Reference)
    )

    def inline_direct_references(item: EBNF_Item) -> Tuple[EBNF_Item, bool]:
        return inline_references(item, direct_references)

    # inline direct optionals

    productions, direct_optionals = separate_references_to_inline(
        productions, lambda item: isinstance(item, EBNF_Optional)
    )

    def inline_direct_optionals(item: EBNF_Item) -> Tuple[EBNF_Item, bool]:
        return inline_references(item, direct_optionals)

    # inline choice of 3 or fewer references to literals

    def is_short_choice_of_literals(item: EBNF_Item) -> bool:
        return (
            isinstance(item, EBNF_Choice)
            and len(item.inner) <= 3
            and all(
                is_literal_reference(inner_item) for inner_item in item.inner
            )
        )

    productions, short_choice_of_literals = separate_references_to_inline(
        productions, is_short_choice_of_literals
    )

    def inline_short_choice_of_literals(
        item: EBNF_Item,
    ) -> Tuple[EBNF_Item, bool]:
        return inline_references(item, short_choice_of_literals)

    # inline sequence of 2 with at least 1 literal

    def is_short_sequence_with_literal(item: EBNF_Item) -> bool:
        return (
            isinstance(item, EBNF_Sequence)
            and len(item.inner) <= 2
            and sum(
                is_literal_reference(inner_item) for inner_item in item.inner
            )
            > 0
        )

    productions, short_sequence_with_literal = separate_references_to_inline(
        productions, is_short_sequence_with_literal
    )

    def inline_short_sequence_with_literal(
        item: EBNF_Item,
    ) -> Tuple[EBNF_Item, bool]:
        return inline_references(item, short_sequence_with_literal)

    # inline paren sequences

    def is_paren_reference(item: EBNF_Item) -> bool:
        return (
            isinstance(item, EBNF_Sequence)
            and len(item.inner) <= 4
            and (
                (
                    is_reference_to(item.inner[0], 'LBRACE')
                    and is_reference_to(item.inner[-1], 'RBRACE')
                )
                or (
                    is_reference_to(item.inner[0], 'LBRACKET')
                    and is_reference_to(item.inner[-1], 'RBRACKET')
                )
                or (
                    is_reference_to(item.inner[0], 'LPAREN')
                    and is_reference_to(item.inner[-1], 'RPAREN')
                )
            )
        )

    productions, paren_references = separate_references_to_inline(
        productions, is_paren_reference
    )

    def inline_paren_references(item: EBNF_Item) -> Tuple[EBNF_Item, bool]:
        return inline_references(item, paren_references)

    # substitute multi-items with a single item

    def substitute_multi_item_single(item: EBNF_Item) -> Tuple[EBNF_Item, bool]:

        if isinstance(item, EBNF_Multiple) and len(item.inner) == 1:
            return item.inner[0], True

        return item, False

    # substitute choices of optionals with optional of choice

    def substitute_choice_of_options(item: EBNF_Item) -> Tuple[EBNF_Item, bool]:

        if isinstance(item, EBNF_Choice):
            inner_options = [
                inner_item
                for inner_item in item.inner
                if isinstance(inner_item, EBNF_Optional)
            ]

            if len(inner_options) == len(item.inner):
                return (
                    EBNF_Optional(
                        EBNF_Choice(
                            [
                                inner_option.inner
                                for inner_option in inner_options
                            ]
                        )
                    ),
                    True,
                )

        return item, False

    # apply replacements until no changes are made

    def replace_repeatedly_helper(
        item: EBNF_Item,
        funcs: List[Callable[[EBNF_Item], Tuple[EBNF_Item, bool]]],
    ) -> EBNF_Item:

        changed = True
        while changed:
            changed = False
            for func in funcs:
                item, curr_changed = func(item)
                changed = changed or curr_changed
        return item

    def replace_repeatedly(item: EBNF_Item) -> EBNF_Item:
        return replace_repeatedly_helper(
            item,
            [
                inline_direct_references,
                inline_direct_optionals,
                inline_short_choice_of_literals,
                inline_short_sequence_with_literal,
                inline_paren_references,
                substitute_multi_item_single,
                substitute_choice_of_options,
            ],
        )

    def replace_recursively(item: EBNF_Item) -> EBNF_Item:
        # replace parent before and after children
        # before children handles recursive inlining
        # after children handles recursive substitution
        item = replace_repeatedly(item)

        if isinstance(item, EBNF_Single):
            item.inner = replace_recursively(item.inner)
            item = replace_repeatedly(item)
        elif isinstance(item, EBNF_Multiple):
            item.inner = [
                replace_recursively(inner_item) for inner_item in item.inner
            ]
            item = replace_repeatedly(item)

        return item

    return [
        EBNF_Production(production.name, replace_recursively(production.item))
        for production in productions
    ]


def to_ebnf(spec: parsing.Spec, path: pathlib.Path):
    ebnf_productions: List[EBNF_Production] = []

    # add token productions
    for token, token_spec in spec._tokens.items():
        if token in ['<e>', '<$>']:
            continue
        ebnf_productions.append(EBNF_Production(token, EBNF_Literal(token)))

    # add nonterm productions
    nonterm_productions: Dict[str, List[List[EBNF_Reference]]] = {}

    has_production = {
        **{token: True for token in spec._tokens},
        **{nonterm: False for nonterm in spec._nonterms},
    }

    for production in spec._productions:
        prod_name = str(production.lhs)
        if prod_name == '<S>':
            continue

        item_list: List[EBNF_Reference] = [
            EBNF_Reference(item.name) for item in production.rhs
        ]

        has_production[prod_name] = True

        if prod_name not in nonterm_productions:
            nonterm_productions[prod_name] = []
        nonterm_productions[prod_name].append(item_list)

    for prod_name, item_lists in nonterm_productions.items():
        # if a production only refers to nonterminals with no productions
        # remove it, since it does nothing

        nonterm_productions[prod_name] = [
            item_list
            for item_list in item_lists
            if
            # refers to token or nonterm with productions
            any(has_production[item.name] for item in item_list) or
            # keep empty reductions, handled later as an optional
            item_list == []
        ]

    for prod_name, item_lists in nonterm_productions.items():
        if [] in item_lists:
            # optional nonterm
            item_lists = [
                item_list for item_list in item_lists if item_list != []
            ]
            ebnf_productions.append(
                EBNF_Production(
                    prod_name,
                    ebnf_single_or_choice(
                        [
                            EBNF_Optional(ebnf_single_or_sequence(item_list))
                            for item_list in item_lists
                        ]
                    ),
                )
            )
        else:
            ebnf_productions.append(
                EBNF_Production(
                    prod_name,
                    ebnf_single_or_choice(
                        [
                            ebnf_single_or_sequence(item_list)
                            for item_list in item_lists
                        ]
                    ),
                )
            )

    # repeatedly simplify until no simplifications are made
    while True:
        count = len(ebnf_productions)
        ebnf_productions = simplify_productions(ebnf_productions)
        if count == len(ebnf_productions):
            break

    # output
    with open(path / 'grammar.iso.ebnf', 'w') as file:
        file.write('\n'.join(to_iso_ebnf(ebnf_productions)))
    with open(path / 'grammar.w3c.ebnf', 'w') as file:
        file.write('\n'.join(to_w3c_ebnf(ebnf_productions)))
