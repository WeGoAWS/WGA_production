"""Utility functions for AWS Documentation MCP integration."""

import re
import json
from typing import Any, Dict, List, Optional

# 필요한 markdownify 라이브러리 가져오기
try:
    import markdownify
except ImportError:
    # 라이브러리 미설치 시 더미 함수로 대체
    def markdownify(html, **kwargs):
        return html

def extract_content_from_html(html: str) -> str:
    """HTML 콘텐츠를 마크다운 형식으로 추출하고 변환합니다."""
    if not html:
        return '<e>Empty HTML content</e>'

    try:
        # BeautifulSoup을 사용하여 HTML 정리
        from bs4 import BeautifulSoup

        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(html, 'html.parser')

        # 메인 콘텐츠 영역 찾기
        main_content = None

        # AWS 문서의 일반적인 콘텐츠 컨테이너 선택자
        content_selectors = [
            'main',
            'article',
            '#main-content',
            '.main-content',
            '#content',
            '.content',
            "div[role='main']",
            '#awsdocs-content',
            '.awsui-article',
        ]

        # 공통 선택자를 사용하여 메인 콘텐츠 찾기
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                main_content = content
                break

        # 메인 콘텐츠를 찾지 못한 경우 본문 사용
        if not main_content:
            main_content = soup.body if soup.body else soup

        # 메인 콘텐츠에 있을 수 있는 탐색 요소 제거
        nav_selectors = [
            'noscript',
            '.prev-next',
            '#main-col-footer',
            '.awsdocs-page-utilities',
            '#quick-feedback-yes',
            '#quick-feedback-no',
            '.page-loading-indicator',
            '#tools-panel',
            '.doc-cookie-banner',
            'awsdocs-copyright',
            'awsdocs-thumb-feedback',
        ]

        for selector in nav_selectors:
            for element in main_content.select(selector):
                element.decompose()

        # 스트립할 태그 정의 - 출력에 포함하지 않을 요소
        tags_to_strip = [
            'script',
            'style',
            'noscript',
            'meta',
            'link',
            'footer',
            'nav',
            'aside',
            'header',
            # AWS 문서 특정 요소
            'awsdocs-cookie-consent-container',
            'awsdocs-feedback-container',
            'awsdocs-page-header',
            'awsdocs-page-header-container',
            'awsdocs-filter-selector',
            'awsdocs-breadcrumb-container',
            'awsdocs-page-footer',
            'awsdocs-page-footer-container',
            'awsdocs-footer',
            'awsdocs-cookie-banner',
            # 일반적인 불필요한 요소
            'js-show-more-buttons',
            'js-show-more-text',
            'feedback-container',
            'feedback-section',
            'doc-feedback-container',
            'doc-feedback-section',
            'warning-container',
            'warning-section',
            'cookie-banner',
            'cookie-notice',
            'copyright-section',
            'legal-section',
            'terms-section',
        ]

        # 정리된 HTML 콘텐츠에 markdownify 사용
        # markdownify 라이브러리가 없는 경우, 단순 텍스트 변환으로 대체
        try:
            content = markdownify.markdownify(
                str(main_content),
                heading_style="ATX",
                autolinks=True,
                default_title=True,
                escape_asterisks=True,
                escape_underscores=True,
                newline_style='SPACES',
                strip=tags_to_strip,
            )
        except (NameError, AttributeError):
            # markdownify가 없는 경우 간단한 텍스트 추출 시도
            content = main_content.get_text(separator='\n\n', strip=True)

        if not content:
            return '<e>Page failed to be simplified from HTML</e>'

        return content
    except Exception as e:
        return f'<e>Error converting HTML to Markdown: {str(e)}</e>'


def is_html_content(page_raw: str, content_type: str) -> bool:
    """콘텐츠가 HTML인지 확인합니다."""
    return '<html' in page_raw[:100] or 'text/html' in content_type or not content_type


def format_documentation_result(url: str, content: str, start_index: int, max_length: int) -> str:
    """페이지네이션 정보로 문서 결과 포맷팅"""
    original_length = len(content)

    if start_index >= original_length:
        return f'AWS Documentation from {url}:\n\n<e>No more content available.</e>'

    # 콘텐츠 길이를 초과하지 않도록 끝 인덱스 계산
    end_index = min(start_index + max_length, original_length)
    truncated_content = content[start_index:end_index]

    if not truncated_content:
        return f'AWS Documentation from {url}:\n\n<e>No more content available.</e>'

    actual_content_length = len(truncated_content)
    remaining_content = original_length - (start_index + actual_content_length)

    result = f'AWS Documentation from {url}:\n\n{truncated_content}'

    # 남은 콘텐츠가 있는 경우에만 계속 가져오기 위한 프롬프트 추가
    if remaining_content > 0:
        next_start = start_index + actual_content_length
        result += f'\n\n<e>Content truncated. Call the read_documentation tool with start_index={next_start} to get more content.</e>'

    return result


def parse_recommendation_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """추천 API 응답을 파싱하여 결과 객체로 변환"""
    results = []

    # 높은 평가를 받은 추천 처리
    if 'highlyRated' in data and 'items' in data['highlyRated']:
        for item in data['highlyRated']['items']:
            context = item.get('abstract') if 'abstract' in item else None

            results.append({
                "url": item.get('url', ''),
                "title": item.get('assetTitle', ''),
                "context": context
            })

    # 여정 추천 처리 (의도별로 구성)
    if 'journey' in data and 'items' in data['journey']:
        for intent_group in data['journey']['items']:
            intent = intent_group.get('intent', '')
            if 'urls' in intent_group:
                for url_item in intent_group['urls']:
                    # 컨텍스트의 일부로 의도 추가
                    context = f'Intent: {intent}' if intent else None

                    results.append({
                        "url": url_item.get('url', ''),
                        "title": url_item.get('assetTitle', ''),
                        "context": context
                    })

    # 새 콘텐츠 추천 처리
    if 'new' in data and 'items' in data['new']:
        for item in data['new']['items']:
            # 컨텍스트에 "새 콘텐츠" 레이블 추가
            date_created = item.get('dateCreated', '')
            context = f'New content added on {date_created}' if date_created else 'New content'

            results.append({
                "url": item.get('url', ''),
                "title": item.get('assetTitle', ''),
                "context": context
            })

    # 유사 추천 처리
    if 'similar' in data and 'items' in data['similar']:
        for item in data['similar']['items']:
            context = item.get('abstract') if 'abstract' in item else 'Similar content'

            results.append({
                "url": item.get('url', ''),
                "title": item.get('assetTitle', ''),
                "context": context
            })

    return results