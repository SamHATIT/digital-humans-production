"""
Tests unitaires pour Git Service extensions - BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §6.7
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from app.services.git_service import GitService


class TestGitExtensions:
    """Tests pour les extensions Git selon spec §6.7."""
    
    def test_create_branch_exists(self):
        """Spec: create_branch() pour branches de phase"""
        service = GitService.__new__(GitService)
        assert hasattr(service, 'create_branch')
        assert callable(service.create_branch)
    
    def test_revert_merge_exists(self):
        """Spec: revert_merge() pour rollback"""
        service = GitService.__new__(GitService)
        assert hasattr(service, 'revert_merge')
        assert callable(service.revert_merge)
    
    def test_tag_exists(self):
        """Spec: tag() pour marquer les releases"""
        service = GitService.__new__(GitService)
        assert hasattr(service, 'tag') or hasattr(service, 'create_tag')
    
    def test_commit_files_exists(self):
        """Spec: commit_files() pour commiter les fichiers"""
        service = GitService.__new__(GitService)
        assert hasattr(service, 'commit_files') or hasattr(service, 'commit')
    
    def test_get_pr_files_exists(self):
        """Spec: get_pr_files() pour lister fichiers d'une PR"""
        service = GitService.__new__(GitService)
        assert hasattr(service, 'get_pr_files')
        assert callable(service.get_pr_files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
